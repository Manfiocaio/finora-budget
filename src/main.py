"""Finora Budget - controle financeiro pessoal com contas individuais."""
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

import mysql.connector
from PIL import Image, ImageOps, UnidentifiedImageError
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
from calculos import (CATEGORIAS, INDEXADORES_INVESTIMENTO, PRODUTOS_INVESTIMENTO, TIPOS,
                      calcular_saldo, converter_valor, formatar_brl, mes_valido,
                      percentual_meta, validar_investimento, validar_meta, validar_movimentacao)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
PASTA_FOTOS_PERFIL = os.path.join(app.instance_path, "fotos_perfil")
app.config.update(
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "0") == "1",
)
app.jinja_env.filters["brl"] = formatar_brl
app.jinja_env.filters["data_br"] = lambda d: d.strftime("%d/%m/%Y") if d else ""


def _grafico(linhas):
    """Lista de categorias -> JSON para o gráfico SVG (static/app.js)."""
    return json.dumps([{"nome": l["categoria"], "valor": float(l["total"])} for l in linhas])


def _mes_ou_none(texto):
    return texto if mes_valido(texto) else None


def _saldo_disponivel(user_id):
    receitas, despesas = db.totais(user_id)
    return calcular_saldo(receitas, despesas) - Decimal(db.saldo_investido(user_id) or 0)


_PERIODOS_GRAFICO = (
    ("1d", "1 dia"),
    ("1s", "1 semana"),
    ("1m", "1 mês"),
    ("2m", "2 meses"),
    ("3m", "3 meses"),
    ("6m", "6 meses"),
    ("1a", "1 ano"),
    ("2a", "2 anos"),
    ("3a", "3 anos"),
    ("5a", "5 anos"),
    ("10a", "10 anos"),
    ("max", "Todo o histórico"),
)


def _subtrair_meses(data_, meses):
    mes_absoluto = data_.year * 12 + data_.month - 1 - meses
    ano, mes_zero = divmod(mes_absoluto, 12)
    mes = mes_zero + 1
    ultimo_dia = (date(ano + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)).day
    return date(ano, mes, min(data_.day, ultimo_dia))


def _intervalo_grafico(args):
    hoje = date.today()
    inicio_texto = args.get("inicio", "").strip()
    fim_texto = args.get("fim", "").strip()
    periodo = args.get("periodo", "6m")
    if inicio_texto or fim_texto:
        try:
            inicio = date.fromisoformat(inicio_texto) if inicio_texto else date.fromisoformat(fim_texto)
            fim = date.fromisoformat(fim_texto) if fim_texto else inicio
        except ValueError as exc:
            raise ValueError("Informe datas válidas para o período do gráfico.") from exc
        if inicio.isoformat() != (inicio_texto or fim_texto) or fim.isoformat() != (fim_texto or inicio_texto):
            raise ValueError("Informe datas válidas para o período do gráfico.")
        if fim < inicio:
            raise ValueError("A data final precisa ser igual ou posterior à data inicial.")
        if inicio < date(1000, 1, 1):
            raise ValueError("A data inicial precisa ser a partir de 01/01/1000.")
        return inicio, fim, "personalizado"

    if periodo == "max":
        return date(1000, 1, 1), hoje, periodo
    if periodo == "1d":
        inicio = hoje
    elif periodo == "1s":
        inicio = hoje - timedelta(days=6)
    elif periodo.endswith("m") and periodo[:-1].isdigit():
        inicio = _subtrair_meses(hoje, int(periodo[:-1]))
    elif periodo.endswith("a") and periodo[:-1].isdigit():
        inicio = _subtrair_meses(hoje, int(periodo[:-1]) * 12)
    else:
        raise ValueError("Escolha um período válido para o gráfico.")
    if periodo not in {opcao[0] for opcao in _PERIODOS_GRAFICO}:
        raise ValueError("Escolha um período válido para o gráfico.")
    return inicio, hoje, periodo


def _grafico_saldo(user_id, inicio, fim):
    eventos = db.eventos_saldo(user_id, fim)
    dias = (fim - inicio).days + 1
    granularidade = "dia" if dias <= 90 else "semana" if dias <= 730 else "mês"
    saldo = Decimal("0")
    candles = {}

    for evento in eventos:
        data_evento = evento["data"]
        delta = Decimal(str(evento["delta"] or 0))
        if data_evento < inicio:
            saldo += delta
            continue
        if granularidade == "dia":
            chave = data_evento
        elif granularidade == "semana":
            chave = data_evento - timedelta(days=data_evento.weekday())
        else:
            chave = data_evento.replace(day=1)
        if chave not in candles:
            candles[chave] = {
                "data": data_evento.isoformat(),
                "abertura": float(saldo),
                "maxima": float(saldo),
                "minima": float(saldo),
                "fechamento": float(saldo),
            }
        saldo += delta
        vela = candles[chave]
        vela["maxima"] = max(vela["maxima"], float(saldo))
        vela["minima"] = min(vela["minima"], float(saldo))
        vela["fechamento"] = float(saldo)
        vela["data"] = data_evento.isoformat()

    if not candles and eventos:
        candles[inicio] = {
            "data": inicio.isoformat(),
            "abertura": float(saldo),
            "maxima": float(saldo),
            "minima": float(saldo),
            "fechamento": float(saldo),
        }
    dados = [candles[chave] for chave in sorted(candles)]
    return json.dumps(dados), granularidade


@app.errorhandler(mysql.connector.Error)
@app.errorhandler(sqlite3.Error)
def erro_banco(e):
    return render_template("erro.html", detalhe=str(e)), 500


db.init_db()


@app.before_request
def proteger_rotas():
    if request.method == "POST":
        token = session.get("_csrf_token", "")
        submitted = request.form.get("_csrf_token", "")
        if not token or not hmac.compare_digest(token, submitted):
            abort(400)

    if request.endpoint in {
        "login", "cadastro", "boas_vindas", "logout", "static", "favicon"
    } or request.endpoint is None:
        return None

    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login", next=request.full_path.rstrip("?")))

    g.usuario = db.obter_usuario(user_id)
    if g.usuario is None:
        session.clear()
        return redirect(url_for("login"))
    if not g.usuario.get("nome") and request.endpoint != "boas_vindas":
        return redirect(url_for("boas_vindas"))
    return None


def _proximo_destino():
    destino = request.args.get("next", "")
    parsed = urlsplit(destino)
    if destino.startswith("/") and not destino.startswith("//") and not parsed.netloc and not parsed.scheme:
        return destino
    return url_for("dashboard")


def _email_valido(email):
    return len(email) <= 254 and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) is not None


@app.context_processor
def globais():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return {
        "categorias": CATEGORIAS,
        "hoje": date.today().isoformat(),
        "csrf_token": session["_csrf_token"],
        "usuario_atual": getattr(g, "usuario", None),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    erro = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        usuario = db.obter_usuario_por_email(email) if len(senha) <= 128 else None
        if usuario and check_password_hash(usuario["senha_hash"], senha):
            session.clear()
            session.permanent = True
            session["user_id"] = usuario["id"]
            flash("Login realizado com sucesso.", "ok")
            if not usuario.get("nome"):
                return redirect(url_for("boas_vindas"))
            return redirect(_proximo_destino())
        erro = "E-mail ou senha incorretos."
    return render_template("login.html", erro=erro)


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    erros = []
    form = {"email": ""}
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""
        confirmacao = request.form.get("confirmacao") or ""
        form["email"] = email
        if not _email_valido(email):
            erros.append("Informe um e-mail válido.")
        if len(senha) < 8:
            erros.append("A senha deve ter pelo menos 8 caracteres.")
        elif len(senha) > 128:
            erros.append("A senha deve ter no máximo 128 caracteres.")
        if senha != confirmacao:
            erros.append("As senhas não coincidem.")
        if not erros:
            user_id = db.criar_usuario(email, generate_password_hash(senha))
            if user_id is None:
                erros.append("Já existe uma conta com esse e-mail.")
            else:
                session.clear()
                session.permanent = True
                session["user_id"] = user_id
                return redirect(url_for("boas_vindas"))
    return render_template("cadastro.html", erros=erros, form=form)


@app.route("/boas-vindas", methods=["GET", "POST"])
def boas_vindas():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))
    usuario = db.obter_usuario(user_id)
    if usuario is None:
        session.clear()
        return redirect(url_for("login"))
    if usuario.get("nome"):
        return redirect(url_for("dashboard"))

    erros = []
    nome = ""
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        if not nome:
            erros.append("Digite o nome pelo qual prefere ser chamado.")
        elif len(nome) > 80:
            erros.append("O nome deve ter no máximo 80 caracteres.")
        else:
            db.atualizar_nome_usuario(user_id, nome)
            flash(f"Que bom ter você por aqui, {nome}!", "ok")
            return redirect(url_for("dashboard"))
    return render_template("boas_vindas.html", erros=erros, nome=nome)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "ok")
    return redirect(url_for("login"))


# ---------- Dashboard ----------
@app.route("/")
def dashboard():
    user_id = g.usuario["id"]
    receitas, despesas = db.totais(user_id)
    investido = Decimal(db.saldo_investido(user_id) or 0)
    hora = datetime.now().hour
    saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
    return render_template(
        "dashboard.html", receitas=receitas, despesas=despesas,
        saldo=calcular_saldo(receitas, despesas) - investido,
        investido=investido,
        saudacao=saudacao,
        grafico=_grafico(db.despesas_por_categoria(user_id)),
        recentes=db.listar_movimentacoes(user_id, limite=6))


@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    user_id = g.usuario["id"]
    erros = []
    nome = g.usuario["nome"]
    foto_perfil = g.usuario.get("foto_perfil")
    if request.method == "POST":
        nome = (request.form.get("nome") or "").strip()
        arquivo = request.files.get("foto")
        remover_foto = request.form.get("remover_foto") == "1"
        if not nome:
            erros.append("Informe o nome que deseja usar no Finora.")
        elif len(nome) > 80:
            erros.append("O nome deve ter no máximo 80 caracteres.")
        if arquivo and arquivo.filename and arquivo.mimetype not in {
            "image/jpeg", "image/png", "image/webp"
        }:
            erros.append("Escolha uma imagem PNG, JPEG ou WebP.")

        imagem_processada = None
        if arquivo and arquivo.filename and not erros:
            try:
                conteudo = arquivo.read()
                with Image.open(io.BytesIO(conteudo)) as imagem:
                    if imagem.format not in {"JPEG", "PNG", "WEBP"}:
                        raise ValueError("Formato de imagem não permitido.")
                    if imagem.width * imagem.height > 20_000_000:
                        raise ValueError("A imagem deve ter no máximo 20 megapixels.")
                    imagem.verify()
                with Image.open(io.BytesIO(conteudo)) as imagem:
                    imagem = ImageOps.exif_transpose(imagem).convert("RGB")
                    imagem = ImageOps.fit(
                        imagem, (256, 256), method=Image.Resampling.LANCZOS
                    )
                    imagem_processada = io.BytesIO()
                    imagem.save(imagem_processada, format="WEBP", quality=85, method=6)
            except (UnidentifiedImageError, OSError, ValueError) as exc:
                erros.append(str(exc) or "Não foi possível ler essa imagem.")

        if not erros:
            foto_anterior = foto_perfil
            novo_caminho = None
            if imagem_processada:
                os.makedirs(PASTA_FOTOS_PERFIL, exist_ok=True)
                nome_foto = f"usuario-{user_id}-{secrets.token_hex(8)}.webp"
                caminho = os.path.join(PASTA_FOTOS_PERFIL, nome_foto)
                temporario = caminho + ".tmp"
                with open(temporario, "wb") as foto:
                    foto.write(imagem_processada.getvalue())
                os.replace(temporario, caminho)
                novo_caminho = caminho
                foto_perfil = nome_foto
            elif remover_foto:
                foto_perfil = None
            try:
                db.atualizar_perfil(user_id, nome, foto_perfil)
            except (sqlite3.Error, mysql.connector.Error):
                if novo_caminho and os.path.isfile(novo_caminho):
                    os.remove(novo_caminho)
                raise
            falha_limpeza_foto = False
            if (foto_anterior and foto_anterior != foto_perfil
                    and (imagem_processada or remover_foto)):
                caminho_antigo = os.path.join(PASTA_FOTOS_PERFIL, foto_anterior)
                if os.path.isfile(caminho_antigo):
                    try:
                        os.remove(caminho_antigo)
                    except OSError as exc:
                        app.logger.warning("Não foi possível remover a foto de perfil antiga: %s", exc)
                        falha_limpeza_foto = True
            if falha_limpeza_foto:
                flash("Perfil atualizado, mas a foto anterior não pôde ser removida do armazenamento.", "erro")
            else:
                flash("Seu perfil foi atualizado.", "ok")
            return redirect(url_for("perfil"))

    receitas, despesas = db.totais(user_id)
    return render_template(
        "perfil.html",
        usuario=g.usuario,
        nome=nome,
        foto_perfil=foto_perfil,
        movimentacoes=db.contar_movimentacoes(user_id),
        metas=len(db.listar_metas(user_id)),
        investido=db.saldo_investido(user_id),
        saldo=calcular_saldo(receitas, despesas) - Decimal(db.saldo_investido(user_id) or 0),
        erros=erros,
    ), 400 if erros else 200


@app.get("/perfil/foto")
def foto_perfil():
    nome_arquivo = g.usuario.get("foto_perfil")
    if not nome_arquivo:
        abort(404)
    return send_from_directory(PASTA_FOTOS_PERFIL, nome_arquivo, mimetype="image/webp")


@app.get("/favicon.svg")
def favicon():
    return send_from_directory(app.static_folder, "favicon.svg", mimetype="image/svg+xml")


# ---------- Movimentações ----------
@app.route("/movimentacoes")
def movimentacoes():
    user_id = g.usuario["id"]
    mes = _mes_ou_none(request.args.get("mes"))
    tipo = request.args.get("tipo") if request.args.get("tipo") in TIPOS else None
    return render_template("movimentacoes.html", lista=db.listar_movimentacoes(user_id, mes, tipo),
                           mes=mes or "", tipo=tipo or "", form={}, erros=[])


@app.route("/movimentacoes/nova", methods=["POST"])
def nova_movimentacao():
    dados, erros = validar_movimentacao(request.form)
    if erros:
        return render_template("movimentacoes.html", lista=db.listar_movimentacoes(g.usuario["id"]),
                               mes="", tipo="", form=request.form, erros=erros), 400
    db.criar_movimentacao(g.usuario["id"], dados)
    flash("Movimentação cadastrada com sucesso.", "ok")
    return redirect(url_for("movimentacoes"))


@app.route("/movimentacoes/<int:id_>/editar", methods=["GET", "POST"])
def editar_movimentacao(id_):
    user_id = g.usuario["id"]
    mov = db.obter_movimentacao(user_id, id_) or abort(404)
    if request.method == "POST":
        dados, erros = validar_movimentacao(request.form)
        if not erros:
            db.atualizar_movimentacao(user_id, id_, dados)
            flash("Movimentação atualizada.", "ok")
            return redirect(url_for("movimentacoes"))
        return render_template("editar_movimentacao.html", form=request.form,
                               id_=id_, erros=erros), 400
    form = {"descricao": mov["descricao"], "valor": f"{mov['valor']:.2f}".replace(".", ","),
            "tipo": mov["tipo"], "categoria": mov["categoria"], "data": mov["data"].isoformat()}
    return render_template("editar_movimentacao.html", form=form, id_=id_, erros=[])


@app.route("/movimentacoes/<int:id_>/excluir", methods=["POST"])
def excluir_movimentacao(id_):
    db.excluir_movimentacao(g.usuario["id"], id_)
    flash("Movimentação excluída.", "ok")
    return redirect(url_for("movimentacoes"))


# ---------- Relatórios ----------
@app.route("/relatorios")
def relatorios():
    user_id = g.usuario["id"]
    mes = _mes_ou_none(request.args.get("mes")) or date.today().strftime("%Y-%m")
    try:
        inicio_grafico, fim_grafico, periodo_grafico = _intervalo_grafico(request.args)
    except ValueError as exc:
        abort(400, description=str(exc))
    receitas, despesas = db.totais(user_id, mes)
    investimentos = db.investimentos_aplicados_no_mes(user_id, mes)
    resgates = db.investimentos_resgatados_no_mes(user_id, mes)
    maior = max(Decimal(receitas or 0), Decimal(despesas or 0), Decimal("0.01"))
    dados_grafico, granularidade_grafico = _grafico_saldo(
        user_id, inicio_grafico, fim_grafico
    )
    return render_template(
        "relatorios.html", mes=mes, receitas=receitas, despesas=despesas,
        investimentos=investimentos, resgates=resgates,
        saldo=calcular_saldo(receitas, despesas) - Decimal(db.saldo_investido(user_id) or 0),
        pct_receitas=float(Decimal(receitas or 0) / maior * 100),
        pct_despesas=float(Decimal(despesas or 0) / maior * 100),
        grafico=_grafico(db.despesas_por_categoria(user_id, mes)),
        dados_grafico=dados_grafico,
        granularidade_grafico=granularidade_grafico,
        periodo_grafico=periodo_grafico,
        periodos_grafico=_PERIODOS_GRAFICO,
        inicio_grafico=inicio_grafico.isoformat() if periodo_grafico == "personalizado" else "",
        fim_grafico=fim_grafico.isoformat() if periodo_grafico == "personalizado" else "",
    )


# ---------- Metas ----------
def _metas_com_progresso():
    metas = db.listar_metas(g.usuario["id"])
    saldo = _saldo_disponivel(g.usuario["id"])
    for m in metas:
        if m["acompanhar_saldo"]:
            m["valor_acumulado"] = saldo
        m["pct"] = percentual_meta(m["valor_acumulado"], m["valor_objetivo"])
        m["barra"] = min(m["pct"], 100)
    return metas


@app.route("/metas")
def metas():
    user_id = g.usuario["id"]
    return render_template(
        "metas.html", lista=_metas_com_progresso(), form={}, erros=[],
        saldo_disponivel=_saldo_disponivel(user_id),
        pode_vincular_saldo=db.meta_que_acompanha_saldo(user_id) is None,
        permitir_vinculo_saldo=True,
    )


@app.route("/metas/nova", methods=["POST"])
def nova_meta():
    dados, erros = validar_meta(request.form)
    if erros:
        return render_template("metas.html", lista=_metas_com_progresso(),
                               form=request.form, erros=erros,
                               saldo_disponivel=_saldo_disponivel(g.usuario["id"]),
                               pode_vincular_saldo=db.meta_que_acompanha_saldo(g.usuario["id"]) is None,
                               permitir_vinculo_saldo=True), 400
    try:
        db.criar_meta(g.usuario["id"], dados)
    except ValueError as exc:
        flash(str(exc), "erro")
        return redirect(url_for("metas"))
    flash("Meta criada com sucesso.", "ok")
    return redirect(url_for("metas"))


@app.route("/metas/<int:id_>/editar", methods=["GET", "POST"])
def editar_meta(id_):
    user_id = g.usuario["id"]
    meta = db.obter_meta(user_id, id_) or abort(404)
    if request.method == "POST":
        dados, erros = validar_meta(request.form)
        if not erros:
            try:
                db.atualizar_meta(user_id, id_, dados)
            except ValueError as exc:
                flash(str(exc), "erro")
                return redirect(url_for("metas"))
            flash("Meta atualizada.", "ok")
            return redirect(url_for("metas"))
        return render_template(
            "editar_meta.html", form=request.form, id_=id_, erros=erros,
            saldo_disponivel=_saldo_disponivel(user_id),
            pode_vincular_saldo=(not meta["acompanhar_saldo"]
                and db.meta_que_acompanha_saldo(user_id, id_) is None)
                or bool(meta["acompanhar_saldo"]),
            permitir_vinculo_saldo=True,
        ), 400
    form = {"nome": meta["nome"],
            "valor_objetivo": f"{meta['valor_objetivo']:.2f}".replace(".", ","),
            "valor_acumulado": f"{(_saldo_disponivel(user_id) if meta['acompanhar_saldo'] else meta['valor_acumulado']):.2f}".replace(".", ","),
            "acompanhar_saldo": "on" if meta["acompanhar_saldo"] else ""}
    return render_template("editar_meta.html", form=form, id_=id_, erros=[],
                           saldo_disponivel=_saldo_disponivel(user_id),
                           pode_vincular_saldo=(not meta["acompanhar_saldo"]
                               and db.meta_que_acompanha_saldo(user_id, id_) is None)
                               or bool(meta["acompanhar_saldo"]),
                           permitir_vinculo_saldo=True)


@app.route("/metas/<int:id_>/depositar", methods=["POST"])
def depositar_meta(id_):
    valor = converter_valor(request.form.get("valor"))
    user_id = g.usuario["id"]
    meta = db.obter_meta(user_id, id_)
    if meta is None:
        abort(404)
    if meta["acompanhar_saldo"]:
        flash("Esta meta acompanha o saldo disponível automaticamente.", "erro")
        return redirect(url_for("metas"))
    if valor is None or valor <= 0:
        flash("Informe um valor maior que zero para guardar.", "erro")
    else:
        db.somar_meta(user_id, id_, valor)
        flash("Valor adicionado à meta.", "ok")
    return redirect(url_for("metas"))


@app.route("/metas/<int:id_>/excluir", methods=["POST"])
def excluir_meta(id_):
    db.excluir_meta(g.usuario["id"], id_)
    flash("Meta excluída.", "ok")
    return redirect(url_for("metas"))


# ---------- Investimentos ----------
@app.route("/investimentos", methods=["GET", "POST"])
def investimentos():
    user_id = g.usuario["id"]
    erros = []
    form = {}
    if request.method == "POST":
        dados, erros = validar_investimento(request.form)
        form = request.form
        if not erros:
            saldo = _saldo_disponivel(user_id)
            if dados["valor"] > saldo:
                erros.append("O valor aplicado não pode ser maior que o saldo disponível.")
            else:
                db.criar_investimento(user_id, dados)
                flash("Investimento cadastrado. O principal foi descontado do saldo disponível.", "ok")
                return redirect(url_for("investimentos"))
    return render_template(
        "investimentos.html",
        lista=db.listar_investimentos(user_id),
        saldo_disponivel=_saldo_disponivel(user_id),
        total_investido=db.saldo_investido(user_id),
        produtos=PRODUTOS_INVESTIMENTO,
        indexadores=INDEXADORES_INVESTIMENTO,
        form=form,
        erros=erros,
    ), 400 if erros else 200


@app.route("/investimentos/<int:id_>/resgatar", methods=["POST"])
def resgatar_investimento(id_):
    valor = converter_valor(request.form.get("valor"))
    user_id = g.usuario["id"]
    if valor is None or valor <= 0:
        flash("Informe um valor de resgate maior que zero.", "erro")
    elif not db.resgatar_investimento(user_id, id_, valor):
        flash("O investimento não existe na sua conta ou o resgate excede o saldo aplicado.", "erro")
    else:
        flash("Resgate registrado e devolvido ao saldo disponível.", "ok")
    return redirect(url_for("investimentos"))


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")

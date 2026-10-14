"""Finora Budget - controle financeiro pessoal com contas individuais."""
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit

import mysql.connector
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

import database as db
from calculos import (CATEGORIAS, TIPOS, calcular_saldo, converter_valor, formatar_brl,
                      mes_valido, percentual_meta, validar_meta, validar_movimentacao)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
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

    if request.endpoint in {"login", "cadastro", "boas_vindas", "logout", "static"} or request.endpoint is None:
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
    hora = datetime.now().hour
    saudacao = "Bom dia" if hora < 12 else "Boa tarde" if hora < 18 else "Boa noite"
    return render_template(
        "dashboard.html", receitas=receitas, despesas=despesas,
        saldo=calcular_saldo(receitas, despesas),
        saudacao=saudacao,
        grafico=_grafico(db.despesas_por_categoria(user_id)),
        recentes=db.listar_movimentacoes(user_id, limite=6))


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
    receitas, despesas = db.totais(user_id, mes)
    maior = max(Decimal(receitas or 0), Decimal(despesas or 0), Decimal("0.01"))
    return render_template(
        "relatorios.html", mes=mes, receitas=receitas, despesas=despesas,
        saldo=calcular_saldo(receitas, despesas),
        pct_receitas=float(Decimal(receitas or 0) / maior * 100),
        pct_despesas=float(Decimal(despesas or 0) / maior * 100),
        grafico=_grafico(db.despesas_por_categoria(user_id, mes)))


# ---------- Metas ----------
def _metas_com_progresso():
    metas = db.listar_metas(g.usuario["id"])
    for m in metas:
        m["pct"] = percentual_meta(m["valor_acumulado"], m["valor_objetivo"])
        m["barra"] = min(m["pct"], 100)
    return metas


@app.route("/metas")
def metas():
    return render_template("metas.html", lista=_metas_com_progresso(), form={}, erros=[])


@app.route("/metas/nova", methods=["POST"])
def nova_meta():
    dados, erros = validar_meta(request.form)
    if erros:
        return render_template("metas.html", lista=_metas_com_progresso(),
                               form=request.form, erros=erros), 400
    db.criar_meta(g.usuario["id"], dados)
    flash("Meta criada com sucesso.", "ok")
    return redirect(url_for("metas"))


@app.route("/metas/<int:id_>/editar", methods=["GET", "POST"])
def editar_meta(id_):
    user_id = g.usuario["id"]
    meta = db.obter_meta(user_id, id_) or abort(404)
    if request.method == "POST":
        dados, erros = validar_meta(request.form)
        if not erros:
            db.atualizar_meta(user_id, id_, dados)
            flash("Meta atualizada.", "ok")
            return redirect(url_for("metas"))
        return render_template("editar_meta.html", form=request.form, id_=id_, erros=erros), 400
    form = {"nome": meta["nome"],
            "valor_objetivo": f"{meta['valor_objetivo']:.2f}".replace(".", ","),
            "valor_acumulado": f"{meta['valor_acumulado']:.2f}".replace(".", ",")}
    return render_template("editar_meta.html", form=form, id_=id_, erros=[])


@app.route("/metas/<int:id_>/depositar", methods=["POST"])
def depositar_meta(id_):
    valor = converter_valor(request.form.get("valor"))
    user_id = g.usuario["id"]
    if db.obter_meta(user_id, id_) is None:
        abort(404)
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


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")

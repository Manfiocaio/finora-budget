"""Finora Budget - controle financeiro pessoal (Flask + banco local)."""
import json
import os
import sqlite3
from datetime import date
from decimal import Decimal

try:
    import mysql.connector
except ImportError:  # MySQL é opcional em desenvolvimento local
    mysql = None

from flask import Flask, abort, flash, redirect, render_template, request, url_for

import database as db
from calculos import (CATEGORIAS, TIPOS, calcular_saldo, converter_valor, formatar_brl,
                      mes_valido, percentual_meta, validar_meta, validar_movimentacao)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chave-apenas-para-desenvolvimento")
app.jinja_env.filters["brl"] = formatar_brl
app.jinja_env.filters["data_br"] = lambda d: d.strftime("%d/%m/%Y") if d else ""


def _grafico(linhas):
    """Lista de categorias -> JSON para o gráfico SVG (static/app.js)."""
    return json.dumps([{"nome": l["categoria"], "valor": float(l["total"])} for l in linhas])


def _mes_ou_none(texto):
    return texto if mes_valido(texto) else None


if mysql is not None:
    @app.errorhandler(mysql.connector.Error)
    def erro_banco(e):
        return render_template("erro.html", detalhe=str(e)), 500
else:
    @app.errorhandler(sqlite3.Error)
    def erro_banco(e):
        return render_template("erro.html", detalhe=str(e)), 500


db.init_db()


@app.context_processor
def globais():
    return {"categorias": CATEGORIAS, "hoje": date.today().isoformat()}


# ---------- Dashboard ----------
@app.route("/")
def dashboard():
    receitas, despesas = db.totais()
    return render_template(
        "dashboard.html", receitas=receitas, despesas=despesas,
        saldo=calcular_saldo(receitas, despesas),
        grafico=_grafico(db.despesas_por_categoria()),
        recentes=db.listar_movimentacoes(limite=6))


# ---------- Movimentações ----------
@app.route("/movimentacoes")
def movimentacoes():
    mes = _mes_ou_none(request.args.get("mes"))
    tipo = request.args.get("tipo") if request.args.get("tipo") in TIPOS else None
    return render_template("movimentacoes.html", lista=db.listar_movimentacoes(mes, tipo),
                           mes=mes or "", tipo=tipo or "", form={}, erros=[])


@app.route("/movimentacoes/nova", methods=["POST"])
def nova_movimentacao():
    dados, erros = validar_movimentacao(request.form)
    if erros:
        return render_template("movimentacoes.html", lista=db.listar_movimentacoes(),
                               mes="", tipo="", form=request.form, erros=erros), 400
    db.criar_movimentacao(dados)
    flash("Movimentação cadastrada com sucesso.", "ok")
    return redirect(url_for("movimentacoes"))


@app.route("/movimentacoes/<int:id_>/editar", methods=["GET", "POST"])
def editar_movimentacao(id_):
    mov = db.obter_movimentacao(id_) or abort(404)
    if request.method == "POST":
        dados, erros = validar_movimentacao(request.form)
        if not erros:
            db.atualizar_movimentacao(id_, dados)
            flash("Movimentação atualizada.", "ok")
            return redirect(url_for("movimentacoes"))
        return render_template("editar_movimentacao.html", form=request.form,
                               id_=id_, erros=erros), 400
    form = {"descricao": mov["descricao"], "valor": f"{mov['valor']:.2f}".replace(".", ","),
            "tipo": mov["tipo"], "categoria": mov["categoria"], "data": mov["data"].isoformat()}
    return render_template("editar_movimentacao.html", form=form, id_=id_, erros=[])


@app.route("/movimentacoes/<int:id_>/excluir", methods=["POST"])
def excluir_movimentacao(id_):
    db.excluir_movimentacao(id_)
    flash("Movimentação excluída.", "ok")
    return redirect(url_for("movimentacoes"))


# ---------- Relatórios ----------
@app.route("/relatorios")
def relatorios():
    mes = _mes_ou_none(request.args.get("mes")) or date.today().strftime("%Y-%m")
    receitas, despesas = db.totais(mes)
    maior = max(Decimal(receitas or 0), Decimal(despesas or 0), Decimal("0.01"))
    return render_template(
        "relatorios.html", mes=mes, receitas=receitas, despesas=despesas,
        saldo=calcular_saldo(receitas, despesas),
        pct_receitas=float(Decimal(receitas or 0) / maior * 100),
        pct_despesas=float(Decimal(despesas or 0) / maior * 100),
        grafico=_grafico(db.despesas_por_categoria(mes)))


# ---------- Metas ----------
def _metas_com_progresso():
    metas = db.listar_metas()
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
    db.criar_meta(dados)
    flash("Meta criada com sucesso.", "ok")
    return redirect(url_for("metas"))


@app.route("/metas/<int:id_>/editar", methods=["GET", "POST"])
def editar_meta(id_):
    meta = db.obter_meta(id_) or abort(404)
    if request.method == "POST":
        dados, erros = validar_meta(request.form)
        if not erros:
            db.atualizar_meta(id_, dados)
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
    if db.obter_meta(id_) is None:
        abort(404)
    if valor is None or valor <= 0:
        flash("Informe um valor maior que zero para guardar.", "erro")
    else:
        db.somar_meta(id_, valor)
        flash("Valor adicionado à meta.", "ok")
    return redirect(url_for("metas"))


@app.route("/metas/<int:id_>/excluir", methods=["POST"])
def excluir_meta(id_):
    db.excluir_meta(id_)
    flash("Meta excluída.", "ok")
    return redirect(url_for("metas"))


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")

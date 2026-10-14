from datetime import date, timedelta
from decimal import Decimal
import importlib
import html
import io
import json
import os
import re
import sqlite3
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import database as db


def _csrf(response):
    match = re.search(rb'name="_csrf_token" value="([^"]+)"', response.data)
    assert match
    return match.group(1).decode()


def _register(client, email):
    page = client.get("/cadastro")
    response = client.post(
        "/cadastro",
        data={
            "_csrf_token": _csrf(page),
            "email": email,
            "senha": "senha-segura-123",
            "confirmacao": "senha-segura-123",
        },
    )
    assert response.status_code == 302
    assert response.location.endswith("/boas-vindas")

    welcome = client.get("/boas-vindas")
    assert welcome.status_code == 200
    assert b"Como podemos chamar voc\xc3\xaa?" in welcome.data
    return client.post(
        "/boas-vindas",
        data={
            "_csrf_token": _csrf(welcome),
            "nome": email.split("@")[0],
        },
    )


def test_movimentacao_sqlite_isolada_por_usuario(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "finora.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()

    user_a = db.criar_usuario("a@example.com", "hash-a")
    user_b = db.criar_usuario("b@example.com", "hash-b")
    dados = {
        "descricao": "Mercado",
        "valor": Decimal("25.50"),
        "tipo": "despesa",
        "categoria": "Alimentação",
        "data": date(2026, 10, 14),
    }
    db.criar_movimentacao(user_a, dados)

    movimentacoes = db.listar_movimentacoes(user_a)
    assert len(movimentacoes) == 1
    assert movimentacoes[0]["data"] == date(2026, 10, 14)
    assert db.obter_movimentacao(user_a, movimentacoes[0]["id"])["data"] == date(2026, 10, 14)
    assert db.listar_movimentacoes(user_b) == []
    assert db.obter_movimentacao(user_b, movimentacoes[0]["id"]) is None


def test_init_db_migra_schema_sqlite_antigo(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "antigo.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    con = sqlite3.connect(db.SQLITE_DB_PATH)
    con.execute(
        "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, email TEXT NOT NULL, senha_hash TEXT NOT NULL)"
    )
    con.execute(
        "CREATE TABLE movimentacoes (id INTEGER PRIMARY KEY, descricao TEXT, valor REAL, "
        "tipo TEXT, categoria TEXT, data TEXT)"
    )
    con.execute(
        "CREATE TABLE metas (id INTEGER PRIMARY KEY, nome TEXT, valor_objetivo REAL, valor_acumulado REAL)"
    )
    con.commit()
    con.close()

    db.init_db()

    con = sqlite3.connect(db.SQLITE_DB_PATH)
    user_columns = {row[1] for row in con.execute("PRAGMA table_info(usuarios)")}
    movement_columns = {row[1] for row in con.execute("PRAGMA table_info(movimentacoes)")}
    goal_columns = {row[1] for row in con.execute("PRAGMA table_info(metas)")}
    user_columns = {row[1] for row in con.execute("PRAGMA table_info(usuarios)")}
    con.close()
    assert "nome" in user_columns
    assert "foto_perfil" in user_columns
    assert "user_id" in movement_columns
    assert "user_id" in goal_columns


def test_cadastro_login_logout_e_protecao_dos_dados(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()

    main = importlib.import_module("main")
    main.app.config.update(TESTING=True, SECRET_KEY="test-signing-key")
    user_a = main.app.test_client()

    assert user_a.get("/movimentacoes").status_code == 302
    assert _register(user_a, "pessoa-a@example.com").status_code == 302
    home = user_a.get("/")
    assert home.status_code == 200
    assert any(greeting in home.data for greeting in (
        b"Bom dia, pessoa-a.",
        b"Boa tarde, pessoa-a.",
        b"Boa noite, pessoa-a.",
    ))

    page = user_a.get("/movimentacoes")
    movement_response = user_a.post(
        "/movimentacoes/nova",
        data={
            "_csrf_token": _csrf(page),
            "descricao": "Conta privada",
            "valor": "25,50",
            "tipo": "despesa",
            "categoria": "Alimentação",
            "data": "2026-10-14",
        },
    )
    assert movement_response.status_code == 302
    user_a_id = db.obter_usuario_por_email("pessoa-a@example.com")["id"]
    movement_id = db.listar_movimentacoes(user_a_id)[0]["id"]

    page = user_a.get("/metas")
    goal_response = user_a.post(
        "/metas/nova",
        data={
            "_csrf_token": _csrf(page),
            "nome": "Meta privada",
            "valor_objetivo": "1000",
            "valor_acumulado": "",
        },
    )
    assert goal_response.status_code == 302

    user_b = main.app.test_client()
    assert _register(user_b, "pessoa-b@example.com").status_code == 302
    assert b"Conta privada" not in user_b.get("/movimentacoes").data
    assert b"Meta privada" not in user_b.get("/metas").data
    assert user_b.get(f"/movimentacoes/{movement_id}/editar").status_code == 404

    duplicate = main.app.test_client()
    duplicate_page = duplicate.get("/cadastro")
    duplicate_response = duplicate.post(
        "/cadastro",
        data={
            "_csrf_token": _csrf(duplicate_page),
            "email": "pessoa-a@example.com",
            "senha": "senha-segura-123",
            "confirmacao": "senha-segura-123",
        },
    )
    assert duplicate_response.status_code == 200
    assert b"J\xc3\xa1 existe" in duplicate_response.data

    wrong_password = main.app.test_client()
    login_page = wrong_password.get("/login")
    wrong_login_response = wrong_password.post(
        "/login",
        data={
            "_csrf_token": _csrf(login_page),
            "email": "pessoa-b@example.com",
            "senha": "senha-errada",
        },
    )
    assert wrong_login_response.status_code == 200
    assert b"E-mail ou senha incorretos" in wrong_login_response.data

    assert user_b.post(
        "/movimentacoes/nova",
        data={
            "_csrf_token": "invalid-token",
            "descricao": "Sem token CSRF",
            "valor": "1",
            "tipo": "despesa",
            "categoria": "Outros",
            "data": "2026-10-14",
        },
    ).status_code == 400

    page = user_b.get("/")
    logout_response = user_b.post("/logout", data={"_csrf_token": _csrf(page)})
    assert logout_response.status_code == 302
    assert user_b.get("/").status_code == 302

    login_page = user_b.get("/login")
    login_response = user_b.post(
        "/login",
        data={
            "_csrf_token": _csrf(login_page),
            "email": "pessoa-b@example.com",
            "senha": "senha-segura-123",
        },
    )
    assert login_response.status_code == 302
    assert user_b.get("/").status_code == 200


def test_carteira_isolada_resgates_e_meta_vinculada_ao_saldo(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "investimentos.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()

    user_a = db.criar_usuario("investidor-a@example.com", "hash-a")
    user_b = db.criar_usuario("investidor-b@example.com", "hash-b")
    db.atualizar_nome_usuario(user_a, "Investidora")
    db.atualizar_nome_usuario(user_b, "Investidor")
    today = date.today()
    db.criar_movimentacao(user_a, {
        "descricao": "Salário", "valor": Decimal("1000"), "tipo": "receita",
        "categoria": "Salário", "data": today,
    })
    db.criar_movimentacao(user_a, {
        "descricao": "Conta", "valor": Decimal("200"), "tipo": "despesa",
        "categoria": "Contas", "data": today,
    })
    periodo = today.strftime("%Y-%m")
    receitas, despesas = db.totais(user_a, periodo)
    assert Decimal(str(receitas)) == Decimal("1000.0")
    assert Decimal(str(despesas)) == Decimal("200.0")
    assert db.despesas_por_categoria(user_a, periodo)[0]["categoria"] == "Contas"
    db.criar_meta(user_a, {
        "nome": "Reserva", "valor_objetivo": Decimal("2000"),
        "valor_acumulado": Decimal("0"), "acompanhar_saldo": True,
    })
    with pytest.raises(ValueError):
        db.criar_meta(user_a, {
            "nome": "Outra reserva", "valor_objetivo": Decimal("500"),
            "valor_acumulado": Decimal("0"), "acompanhar_saldo": True,
        })
    db.criar_meta(user_b, {
        "nome": "Reserva B", "valor_objetivo": Decimal("500"),
        "valor_acumulado": Decimal("0"), "acompanhar_saldo": True,
    })

    investment_data = {
        "produto": "CDB", "instituicao": "Banco A", "valor": Decimal("300"),
        "indexador": "CDI", "taxa_anual": None, "data_aplicacao": today,
        "vencimento": None,
    }
    db.criar_investimento(user_a, investment_data)
    item = db.listar_investimentos(user_a)[0]
    assert item["data_aplicacao"] == today
    assert db.listar_investimentos(user_b) == []
    assert Decimal(str(db.saldo_investido(user_a))) == Decimal("300.0")
    assert Decimal(str(db.saldo_investido(user_b))) == Decimal("0")
    assert Decimal(str(db.investimentos_aplicados_no_mes(user_a, periodo))) == Decimal("300.0")

    main = importlib.import_module("main")
    main.app.config.update(TESTING=True, SECRET_KEY="test-signing-key")
    client = main.app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user_a
        sess["_csrf_token"] = "test-token"
    assert b"R$ 500,00" in client.get("/metas").data
    portfolio = client.get("/investimentos")
    assert portfolio.status_code == 200
    assert b"Banco A" in portfolio.data
    other_client = main.app.test_client()
    with other_client.session_transaction() as sess:
        sess["user_id"] = user_b
        sess["_csrf_token"] = "other-token"
    assert b"Banco A" not in other_client.get("/investimentos").data
    rejected = client.post("/investimentos", data={
        "_csrf_token": "test-token", "produto": "CDB", "instituicao": "Banco B",
        "valor": "600", "indexador": "CDI", "taxa_anual": "",
        "data_aplicacao": today.isoformat(), "vencimento": "",
    })
    assert rejected.status_code == 400
    assert b"maior que o saldo dispon\xc3\xadvel" in rejected.data

    assert db.resgatar_investimento(user_a, item["id"], Decimal("100"))
    assert not db.resgatar_investimento(user_a, item["id"], Decimal("500"))
    assert Decimal(str(db.saldo_investido(user_a))) == Decimal("200.0")
    assert Decimal(str(db.investimentos_resgatados_no_mes(
        user_a, periodo
    ))) == Decimal("100.0")
    assert b"R$ 600,00" in client.get("/metas").data
    report = client.get(f"/relatorios?mes={today.strftime('%Y-%m')}")
    assert report.status_code == 200
    assert b"Saldo ao longo do tempo" in report.data


def test_perfil_edita_nome_foto_e_estatisticas(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "perfil.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()

    main = importlib.import_module("main")
    main.app.config.update(TESTING=True, SECRET_KEY="test-signing-key")
    monkeypatch.setattr(main, "PASTA_FOTOS_PERFIL", str(tmp_path / "fotos"))
    client = main.app.test_client()
    _register(client, "perfil@example.com")
    user_id = db.obter_usuario_por_email("perfil@example.com")["id"]
    db.criar_movimentacao(user_id, {
        "descricao": "Salário", "valor": Decimal("1500"), "tipo": "receita",
        "categoria": "Salário", "data": date.today(),
    })

    page = client.get("/perfil")
    assert page.status_code == 200
    assert b"Movimenta\xc3\xa7\xc3\xb5es registradas" in page.data
    assert b">1</strong>" in page.data

    imagem = io.BytesIO()
    Image.new("RGB", (32, 24), color="navy").save(imagem, format="PNG")
    imagem.seek(0)
    response = client.post(
        "/perfil",
        data={
            "_csrf_token": _csrf(page),
            "nome": "Perfil atualizado",
            "foto": (imagem, "avatar.png", "image/png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    usuario = db.obter_usuario(user_id)
    assert usuario["nome"] == "Perfil atualizado"
    assert usuario["foto_perfil"].endswith(".webp")
    foto = client.get("/perfil/foto")
    assert foto.status_code == 200
    assert foto.mimetype == "image/webp"
    with Image.open(io.BytesIO(foto.data)) as processada:
        assert processada.size == (256, 256)
    foto.close()

    outra_conta = main.app.test_client()
    outro_id = db.criar_usuario("outro-perfil@example.com", "hash")
    db.atualizar_perfil(outro_id, "Outra pessoa", None)
    with outra_conta.session_transaction() as sess:
        sess["user_id"] = outro_id
    assert outra_conta.get("/perfil/foto").status_code == 404

    page = client.get("/perfil")
    removed = client.post(
        "/perfil",
        data={
            "_csrf_token": _csrf(page),
            "nome": "Perfil atualizado",
            "remover_foto": "1",
        },
    )
    assert removed.status_code == 302
    assert db.obter_usuario(user_id)["foto_perfil"] is None
    assert client.get("/perfil/foto").status_code == 404


def test_relatorio_grafico_saldo_em_barras_e_periodos(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "grafico.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()

    main = importlib.import_module("main")
    main.app.config.update(TESTING=True, SECRET_KEY="test-signing-key")
    client = main.app.test_client()
    _register(client, "grafico@example.com")
    user_id = db.obter_usuario_por_email("grafico@example.com")["id"]
    ontem = date.today() - timedelta(days=1)
    hoje = date.today()
    db.criar_movimentacao(user_id, {
        "descricao": "Renda", "valor": Decimal("2000"), "tipo": "receita",
        "categoria": "Salário", "data": ontem,
    })
    db.criar_movimentacao(user_id, {
        "descricao": "Compra", "valor": Decimal("500"), "tipo": "despesa",
        "categoria": "Outros", "data": hoje,
    })
    db.criar_investimento(user_id, {
        "produto": "CDB", "instituicao": "Banco de teste", "valor": Decimal("600"),
        "indexador": "CDI", "taxa_anual": None,
        "data_aplicacao": ontem, "vencimento": None,
    })
    investimento = db.listar_investimentos(user_id)[0]
    assert db.resgatar_investimento(user_id, investimento["id"], Decimal("100"))

    relatorio = client.get("/relatorios?periodo=1s")
    assert relatorio.status_code == 200
    assert b">Barras</button>" in relatorio.data
    assert b"data-tipo=\"barras\"" in relatorio.data
    match = re.search(rb"data-dados='([^']*)'", relatorio.data)
    assert match
    dados = json.loads(html.unescape(match.group(1).decode()))
    barra_hoje = next(ponto for ponto in dados if ponto["data"] == hoje.isoformat())
    assert barra_hoje == {
        "data": hoje.isoformat(),
        "abertura": 1400.0,
        "maxima": 1400.0,
        "minima": 1000.0,
        "fechamento": 1000.0,
    }

    dia_especifico = client.get(f"/relatorios?inicio={hoje.isoformat()}")
    assert dia_especifico.status_code == 200
    assert f'value="{hoje.isoformat()}"'.encode() in dia_especifico.data
    assert client.get(
        f"/relatorios?inicio={hoje.isoformat()}&fim={ontem.isoformat()}"
    ).status_code == 400

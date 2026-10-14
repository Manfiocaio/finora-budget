from datetime import date
from decimal import Decimal
import importlib
import os
import re
import sys

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

from datetime import date
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import importlib
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import database as db
from calculos import validar_recorrencia


def _isolated_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "planning.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()
    main = importlib.import_module("main")
    main.app.config.update(TESTING=True, SECRET_KEY="planning-tests")
    return main


def _user(email):
    user_id = db.criar_usuario(email, "test-password-hash")
    db.atualizar_nome_usuario(user_id, "Teste")
    return user_id


def _csrf(response):
    match = re.search(rb'name="_csrf_token" value="([^"]+)"', response.data)
    assert match
    return match.group(1).decode()


def test_orcamentos_somam_despesas_do_mes_e_isolam_contas(tmp_path, monkeypatch):
    _isolated_database(tmp_path, monkeypatch)
    user_a = _user("orcamento-a@example.com")
    user_b = _user("orcamento-b@example.com")
    db.salvar_orcamento(user_a, "Alimentação", Decimal("500.00"))
    db.salvar_orcamento(user_b, "Alimentação", Decimal("100.00"))
    db.criar_movimentacao(user_a, {
        "descricao": "Mercado",
        "valor": Decimal("125.50"),
        "tipo": "despesa",
        "categoria": "Alimentação",
        "data": date(2026, 3, 12),
    })
    db.criar_movimentacao(user_a, {
        "descricao": "Salário",
        "valor": Decimal("2000.00"),
        "tipo": "receita",
        "categoria": "Alimentação",
        "data": date(2026, 3, 14),
    })
    db.criar_movimentacao(user_a, {
        "descricao": "Mercado mês anterior",
        "valor": Decimal("40.00"),
        "tipo": "despesa",
        "categoria": "Alimentação",
        "data": date(2026, 2, 28),
    })
    db.criar_movimentacao(user_b, {
        "descricao": "Despesa privada",
        "valor": Decimal("75.00"),
        "tipo": "despesa",
        "categoria": "Alimentação",
        "data": date(2026, 3, 12),
    })

    lista = db.listar_orcamentos(user_a, "2026-03")
    assert len(lista) == 1
    assert lista[0]["categoria"] == "Alimentação"
    assert Decimal(str(lista[0]["gasto"])) == Decimal("125.5")
    assert db.listar_orcamentos(user_b, "2026-03")[0]["gasto"] == 75
    db.salvar_orcamento(user_a, "Alimentação", Decimal("600.00"))
    assert len(db.listar_orcamentos(user_a, "2026-03")) == 1
    assert Decimal(str(db.listar_orcamentos(user_a, "2026-03")[0]["limite"])) == Decimal("600.0")


def test_recorrencias_recuperam_atrasos_sem_duplicacao_e_respeitam_fim(
    tmp_path, monkeypatch
):
    _isolated_database(tmp_path, monkeypatch)
    user_id = _user("recorrencia@example.com")
    db.criar_recorrencia(user_id, {
        "descricao": "Academia",
        "valor": Decimal("89.90"),
        "tipo": "despesa",
        "categoria": "Saúde",
        "frequencia": "semanal",
        "inicio": date(2026, 3, 1),
        "data_fim": date(2026, 3, 31),
    })

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(
            lambda _: db.processar_recorrencias(user_id, date(2026, 3, 31)),
            range(2),
        ))
    assert sorted(resultados) == [0, 5]
    assert db.processar_recorrencias(user_id, date(2026, 3, 31)) == 0
    movimentos = db.listar_movimentacoes(user_id)
    assert [item["data"] for item in reversed(movimentos)] == [
        date(2026, 3, 1),
        date(2026, 3, 8),
        date(2026, 3, 15),
        date(2026, 3, 22),
        date(2026, 3, 29),
    ]
    recorrencia = db.listar_recorrencias(user_id)[0]
    assert recorrencia["proxima_data"] == date(2026, 4, 5)
    assert recorrencia["ativa"] == 0


def test_recorrencia_mensal_preserva_dia_original_no_fim_do_mes(tmp_path, monkeypatch):
    _isolated_database(tmp_path, monkeypatch)
    user_id = _user("mensal@example.com")
    db.criar_recorrencia(user_id, {
        "descricao": "Conta mensal",
        "valor": Decimal("120.00"),
        "tipo": "despesa",
        "categoria": "Contas",
        "frequencia": "mensal",
        "inicio": date(2026, 1, 31),
        "data_fim": date(2026, 3, 31),
    })

    assert db.processar_recorrencias(user_id, date(2026, 3, 31)) == 3
    assert [item["data"] for item in reversed(db.listar_movimentacoes(user_id))] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert db.listar_recorrencias(user_id)[0]["proxima_data"] == date(2026, 4, 30)


def test_validacao_de_recorrencia_rejeita_intervalo_invalido(tmp_path, monkeypatch):
    _isolated_database(tmp_path, monkeypatch)
    dados, erros = validar_recorrencia({
        "descricao": "Conta",
        "valor": "80,00",
        "tipo": "despesa",
        "categoria": "Contas",
        "frequencia": "diaria",
        "inicio": "2026-03-20",
        "data_fim": "2026-03-19",
    })

    assert dados["frequencia"] == "diaria"
    assert "Escolha uma frequência válida." in erros
    assert "A data final não pode ser anterior ao primeiro lançamento." in erros


def test_rotas_de_planejamento_sao_autenticadas_e_renderizam(tmp_path, monkeypatch):
    main = _isolated_database(tmp_path, monkeypatch)
    user_id = _user("rotas@example.com")
    client = main.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id

    page = client.get("/orcamentos")
    assert page.status_code == 200
    assert b"Or\xc3\xa7amentos mensais" in page.data
    response = client.post("/orcamentos/salvar", data={
        "_csrf_token": _csrf(page),
        "mes": date.today().strftime("%Y-%m"),
        "categoria": "Moradia",
        "limite": "1500,00",
    })
    assert response.status_code == 302
    assert client.get("/recorrencias").status_code == 200
    assert client.get("/recorrencias").data.count(b"Agendar movimenta") >= 1

    anonymous = main.app.test_client()
    assert anonymous.get("/orcamentos").status_code == 302
    assert anonymous.get("/recorrencias").status_code == 302


def test_recorrencia_agendada_para_hoje_e_lancada_na_proxima_solicitacao(
    tmp_path, monkeypatch
):
    main = _isolated_database(tmp_path, monkeypatch)
    user_id = _user("auto@example.com")
    client = main.app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    page = client.get("/recorrencias")

    response = client.post("/recorrencias/nova", data={
        "_csrf_token": _csrf(page),
        "descricao": "Conta de hoje",
        "valor": "42,00",
        "tipo": "despesa",
        "categoria": "Contas",
        "frequencia": "mensal",
        "inicio": date.today().isoformat(),
        "data_fim": "",
    })
    assert response.status_code == 302
    result = client.get("/recorrencias")
    assert b"lan\xc3\xa7ada(s) automaticamente" in result.data
    assert db.contar_movimentacoes(user_id) == 1
    client.get("/recorrencias")
    assert db.contar_movimentacoes(user_id) == 1

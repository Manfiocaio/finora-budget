from datetime import date
from decimal import Decimal
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import database as db


def test_movimentacao_sqlite_pode_ser_listada_e_editada(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "finora.db"))
    monkeypatch.setattr(db, "_mysql_disponivel", lambda: False)
    db.init_db()

    dados = {
        "descricao": "Mercado",
        "valor": Decimal("25.50"),
        "tipo": "despesa",
        "categoria": "Alimentação",
        "data": date(2026, 10, 14),
    }
    db.criar_movimentacao(dados)

    movimentacoes = db.listar_movimentacoes()
    assert len(movimentacoes) == 1
    assert movimentacoes[0]["data"] == date(2026, 10, 14)
    assert db.obter_movimentacao(movimentacoes[0]["id"])["data"] == date(2026, 10, 14)

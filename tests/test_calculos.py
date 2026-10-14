import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calculos import (calcular_saldo, converter_valor, formatar_brl, mes_valido,
                      percentual_meta, validar_investimento, validar_meta,
                      validar_movimentacao)


def mov(**kw):
    base = {"descricao": "Mercado", "valor": "150,50", "tipo": "despesa",
            "categoria": "Alimentação", "data": "2026-10-14"}
    base.update(kw)
    return base


def test_converter_valor_formatos():
    assert converter_valor("1.234,56") == Decimal("1234.56")
    assert converter_valor("10") == Decimal("10.00")
    assert converter_valor("R$ 5,5") == Decimal("5.50")
    assert converter_valor("abc") is None
    assert converter_valor("") is None
    assert converter_valor("NaN") is None
    assert converter_valor("99999999999") is None


def test_formatar_brl():
    assert formatar_brl(1234.5) == "R$ 1.234,50"
    assert formatar_brl(0) == "R$ 0,00"
    assert formatar_brl(Decimal("-10")) == "-R$ 10,00"


def test_saldo():
    assert calcular_saldo(Decimal("1000"), Decimal("350.25")) == Decimal("649.75")
    assert calcular_saldo(0, Decimal("50")) == Decimal("-50")
    assert calcular_saldo(None, None) == 0


def test_percentual_meta():
    assert percentual_meta(Decimal("250"), Decimal("1000")) == 25.0
    assert percentual_meta(0, Decimal("1000")) == 0.0
    assert percentual_meta(Decimal("1500"), Decimal("1000")) == 150.0
    assert percentual_meta(10, 0) == 0.0


def test_mes_valido():
    assert mes_valido("2026-10")
    assert not mes_valido("2026-13")
    assert not mes_valido("10/2026")
    assert not mes_valido(None)


def test_movimentacao_valida():
    dados, erros = validar_movimentacao(mov())
    assert erros == []
    assert dados["valor"] == Decimal("150.50")
    assert dados["tipo"] == "despesa"


def test_movimentacao_invalida():
    for campo, valor in [("descricao", "  "), ("valor", "0"), ("valor", "-5"), ("valor", "x"),
                         ("tipo", "outro"), ("categoria", "Inexistente"), ("data", "31/02/2026"),
                         ("descricao", "a" * 121)]:
        _, erros = validar_movimentacao(mov(**{campo: valor}))
        assert erros, f"deveria rejeitar {campo}={valor!r}"


def test_meta_valida_e_padrao_zero():
    dados, erros = validar_meta({"nome": "Viagem", "valor_objetivo": "3.000,00"})
    assert erros == []
    assert dados["valor_acumulado"] == Decimal("0.00")


def test_meta_invalida():
    assert validar_meta({"nome": "", "valor_objetivo": "100"})[1]
    assert validar_meta({"nome": "X", "valor_objetivo": "0"})[1]
    assert validar_meta({"nome": "X", "valor_objetivo": "100", "valor_acumulado": "-1"})[1]


def test_meta_vinculada_ignora_valor_manual():
    dados, erros = validar_meta({
        "nome": "Reserva", "valor_objetivo": "5000",
        "valor_acumulado": "inválido", "acompanhar_saldo": "on",
    })
    assert erros == []
    assert dados["acompanhar_saldo"] is True
    assert dados["valor_acumulado"] == Decimal("0.00")


def test_investimento_valido_e_invalido():
    base = {
        "produto": "CDB",
        "instituicao": "Banco Finora",
        "valor": "1.234,50",
        "indexador": "CDI",
        "taxa_anual": "2,5",
        "data_aplicacao": "2026-10-14",
        "vencimento": "2027-10-14",
    }
    dados, erros = validar_investimento(base)
    assert erros == []
    assert dados["valor"] == Decimal("1234.50")
    assert dados["taxa_anual"] == Decimal("2.50")
    assert dados["vencimento"].isoformat() == "2027-10-14"

    _, erros = validar_investimento({**base, "valor": "0", "indexador": "Desconhecido"})
    assert len(erros) >= 2
    _, erros = validar_investimento({**base, "data_aplicacao": "2027-01-01", "vencimento": "2026-01-01"})
    assert any("anterior à aplicação" in erro for erro in erros)

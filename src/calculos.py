"""Cálculos, formatação e validações do Finora Budget (sem acesso ao banco)."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

TIPOS = ("receita", "despesa")
CATEGORIAS = [
    "Alimentação", "Moradia", "Transporte", "Saúde", "Educação",
    "Lazer", "Compras", "Contas", "Salário", "Renda extra", "Outros",
]
PRODUTOS_INVESTIMENTO = (
    "CDB", "LCI", "LCA", "Tesouro Selic", "Tesouro Prefixado",
    "Tesouro IPCA+", "Debênture", "Outro",
)
INDEXADORES_INVESTIMENTO = ("Prefixado", "CDI", "Selic", "IPCA", "Outro")
VALOR_MAXIMO = Decimal("9999999999.99")  # limite do DECIMAL(12,2)


def converter_valor(texto):
    """Converte '1.234,56' ou '1234.56' em Decimal com 2 casas. Retorna None se inválido."""
    if texto is None:
        return None
    t = str(texto).strip().replace("R$", "").replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        v = Decimal(t)
        if not v.is_finite() or abs(v) > VALOR_MAXIMO:
            return None
        return v.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def formatar_brl(valor):
    """Formata como moeda brasileira: R$ 1.234,56."""
    v = Decimal(valor or 0)
    texto = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if v < 0 else f"R$ {texto}"


def calcular_saldo(receitas, despesas):
    return Decimal(receitas or 0) - Decimal(despesas or 0)


def percentual_meta(acumulado, objetivo):
    """Percentual economizado (1 casa decimal). Objetivo inválido retorna 0."""
    obj = Decimal(objetivo or 0)
    if obj <= 0:
        return 0.0
    return round(float(Decimal(acumulado or 0) / obj * 100), 1)


def mes_valido(texto):
    """Aceita 'AAAA-MM' com mês de 01 a 12."""
    return bool(texto) and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", texto) is not None


def validar_movimentacao(form):
    """Retorna (dados, erros). 'dados' só deve ser usado quando 'erros' estiver vazio."""
    erros = []
    descricao = (form.get("descricao") or "").strip()
    tipo = (form.get("tipo") or "").strip()
    categoria = (form.get("categoria") or "").strip()
    valor = converter_valor(form.get("valor"))
    data_txt = (form.get("data") or "").strip()

    if not descricao:
        erros.append("Informe a descrição.")
    elif len(descricao) > 120:
        erros.append("A descrição deve ter no máximo 120 caracteres.")
    if valor is None or valor <= 0:
        erros.append("Informe um valor maior que zero.")
    if tipo not in TIPOS:
        erros.append("Escolha o tipo: receita ou despesa.")
    if categoria not in CATEGORIAS:
        erros.append("Escolha uma categoria válida.")
    try:
        data = datetime.strptime(data_txt, "%Y-%m-%d").date()
    except ValueError:
        data = None
        erros.append("Informe uma data válida.")
    dados = {"descricao": descricao, "valor": valor, "tipo": tipo,
             "categoria": categoria, "data": data}
    return dados, erros


def validar_meta(form):
    """Retorna (dados, erros) para metas. Valor acumulado é opcional (padrão 0)."""
    erros = []
    nome = (form.get("nome") or "").strip()
    objetivo = converter_valor(form.get("valor_objetivo"))
    acompanhar_saldo = form.get("acompanhar_saldo") in ("1", "on", "true")
    acum_txt = (form.get("valor_acumulado") or "").strip()
    acumulado = Decimal("0.00") if acompanhar_saldo or acum_txt == "" else converter_valor(acum_txt)

    if not nome:
        erros.append("Informe o nome da meta.")
    elif len(nome) > 100:
        erros.append("O nome deve ter no máximo 100 caracteres.")
    if objetivo is None or objetivo <= 0:
        erros.append("Informe um valor desejado maior que zero.")
    if acumulado is None or acumulado < 0:
        erros.append("O valor economizado não pode ser negativo.")
    return {
        "nome": nome,
        "valor_objetivo": objetivo,
        "valor_acumulado": acumulado,
        "acompanhar_saldo": acompanhar_saldo,
    }, erros


def validar_investimento(form):
    """Valida os dados de um investimento sem estimar rentabilidade futura."""
    erros = []
    produto = (form.get("produto") or "").strip()
    instituicao = (form.get("instituicao") or "").strip()
    indexador = (form.get("indexador") or "").strip()
    valor = converter_valor(form.get("valor"))
    taxa_txt = (form.get("taxa_anual") or "").strip()
    taxa = None if not taxa_txt else converter_valor(taxa_txt)
    data_txt = (form.get("data_aplicacao") or "").strip()
    vencimento_txt = (form.get("vencimento") or "").strip()

    if produto not in PRODUTOS_INVESTIMENTO:
        erros.append("Escolha um tipo de investimento válido.")
    if not instituicao or len(instituicao) > 100:
        erros.append("Informe uma instituição com até 100 caracteres.")
    if valor is None or valor <= 0:
        erros.append("Informe um valor aplicado maior que zero.")
    if indexador not in INDEXADORES_INVESTIMENTO:
        erros.append("Escolha um indexador válido.")
    if taxa_txt and (taxa is None or taxa < 0 or taxa > 1000):
        erros.append("Informe uma taxa anual entre 0 e 1.000%, ou deixe em branco.")
    try:
        data_aplicacao = datetime.strptime(data_txt, "%Y-%m-%d").date()
    except ValueError:
        data_aplicacao = None
        erros.append("Informe uma data de aplicação válida.")
    try:
        vencimento = datetime.strptime(vencimento_txt, "%Y-%m-%d").date() if vencimento_txt else None
    except ValueError:
        vencimento = None
        erros.append("Informe uma data de vencimento válida.")
    if data_aplicacao and vencimento and vencimento < data_aplicacao:
        erros.append("O vencimento não pode ser anterior à aplicação.")

    return {
        "produto": produto,
        "instituicao": instituicao,
        "valor": valor,
        "indexador": indexador,
        "taxa_anual": taxa,
        "data_aplicacao": data_aplicacao,
        "vencimento": vencimento,
    }, erros

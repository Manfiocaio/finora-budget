"""Acesso ao banco do Finora Budget.

Usa MySQL quando disponível e cai para SQLite automaticamente em ambiente local sem
servidor MySQL.
"""
import os
import sqlite3
from datetime import date
from decimal import Decimal

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv é opcional
    pass


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "finora_budget.db"))


def _mysql_disponivel():
    backend = os.getenv("DB_BACKEND", "auto").lower()
    if backend == "sqlite":
        return False
    if backend == "mysql":
        return True
    try:
        import mysql.connector

        con = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "finora_budget"),
            connection_timeout=2,
        )
        con.close()
        return True
    except Exception:
        return False


def _normalizar_parametro(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _normalizar_parametros(params):
    if isinstance(params, tuple):
        return tuple(_normalizar_parametro(p) for p in params)
    if isinstance(params, list):
        return [_normalizar_parametro(p) for p in params]
    return params


def init_db():
    """Cria a estrutura local se usar SQLite."""
    if _mysql_disponivel():
        return

    con = sqlite3.connect(SQLITE_DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL CHECK(valor > 0),
                tipo TEXT NOT NULL,
                categoria TEXT NOT NULL,
                data TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                valor_objetivo REAL NOT NULL CHECK(valor_objetivo > 0),
                valor_acumulado REAL NOT NULL DEFAULT 0 CHECK(valor_acumulado >= 0)
            )
            """
        )
        con.commit()
    finally:
        con.close()


def conectar():
    if _mysql_disponivel():
        import mysql.connector

        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "finora_budget"),
        )

    return sqlite3.connect(SQLITE_DB_PATH)


def _consultar(sql, params=(), um=False):
    con = conectar()
    try:
        if isinstance(con, sqlite3.Connection):
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            params = _normalizar_parametros(params)
        else:
            cur = con.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchone() if um else cur.fetchall()
        if isinstance(con, sqlite3.Connection):
            if um:
                return _normalizar_linha(dict(rows)) if rows else None
            return [_normalizar_linha(dict(r)) for r in rows]
        return rows
    finally:
        con.close()


def _normalizar_linha(linha):
    if isinstance(linha.get("data"), str):
        linha["data"] = date.fromisoformat(linha["data"])
    return linha


def _executar(sql, params=()):
    con = conectar()
    try:
        cur = con.cursor()
        if isinstance(con, sqlite3.Connection):
            params = _normalizar_parametros(params)
        cur.execute(sql, params)
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def _filtro(mes=None, tipo=None):
    onde, params = [], []
    if mes:
        if _mysql_disponivel():
            onde.append("DATE_FORMAT(`data`, '%%Y-%%m') = %s")
        else:
            onde.append("strftime('%%Y-%%m', data) = ?")
        params.append(mes)
    if tipo:
        onde.append("tipo = %s" if _mysql_disponivel() else "tipo = ?")
        params.append(tipo)
    return (" WHERE " + " AND ".join(onde)) if onde else "", params


# ---------- Movimentações ----------
def listar_movimentacoes(mes=None, tipo=None, limite=None):
    onde, params = _filtro(mes, tipo)
    sql = "SELECT id, descricao, valor, tipo, categoria, `data` FROM movimentacoes" + onde
    sql += " ORDER BY `data` DESC, id DESC"
    if limite:
        sql += " LIMIT %s" if _mysql_disponivel() else " LIMIT ?"
        params.append(int(limite))
    return _consultar(sql, params)


def obter_movimentacao(id_):
    sql = "SELECT id, descricao, valor, tipo, categoria, `data` FROM movimentacoes WHERE id = %s"
    if not _mysql_disponivel():
        sql = "SELECT id, descricao, valor, tipo, categoria, `data` FROM movimentacoes WHERE id = ?"
    return _consultar(sql, (id_,), um=True)


def criar_movimentacao(d):
    sql = (
        "INSERT INTO movimentacoes (descricao, valor, tipo, categoria, `data`) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    if not _mysql_disponivel():
        sql = (
            "INSERT INTO movimentacoes (descricao, valor, tipo, categoria, data) "
            "VALUES (?, ?, ?, ?, ?)"
        )
    _executar(sql, (d["descricao"], d["valor"], d["tipo"], d["categoria"], d["data"]))


def atualizar_movimentacao(id_, d):
    sql = (
        "UPDATE movimentacoes SET descricao=%s, valor=%s, tipo=%s, categoria=%s, "
        "`data`=%s WHERE id=%s"
    )
    if not _mysql_disponivel():
        sql = (
            "UPDATE movimentacoes SET descricao=?, valor=?, tipo=?, categoria=?, "
            "data=? WHERE id=?"
        )
    _executar(sql, (d["descricao"], d["valor"], d["tipo"], d["categoria"], d["data"], id_))


def excluir_movimentacao(id_):
    sql = "DELETE FROM movimentacoes WHERE id = %s"
    if not _mysql_disponivel():
        sql = "DELETE FROM movimentacoes WHERE id = ?"
    _executar(sql, (id_,))


def totais(mes=None):
    """Soma de receitas e despesas."""
    onde, params = _filtro(mes)
    sql = "SELECT tipo, SUM(valor) AS total FROM movimentacoes" + onde + " GROUP BY tipo"
    linhas = _consultar(sql, params)
    r = {l["tipo"]: l["total"] for l in linhas}
    return r.get("receita", 0), r.get("despesa", 0)


def despesas_por_categoria(mes=None):
    onde, params = _filtro(mes, "despesa")
    sql = "SELECT categoria, SUM(valor) AS total FROM movimentacoes" + onde + " GROUP BY categoria ORDER BY total DESC"
    return _consultar(sql, params)


# ---------- Metas ----------
def listar_metas():
    sql = "SELECT id, nome, valor_objetivo, valor_acumulado FROM metas ORDER BY id DESC"
    return _consultar(sql)


def obter_meta(id_):
    sql = "SELECT id, nome, valor_objetivo, valor_acumulado FROM metas WHERE id = %s"
    if not _mysql_disponivel():
        sql = "SELECT id, nome, valor_objetivo, valor_acumulado FROM metas WHERE id = ?"
    return _consultar(sql, (id_,), um=True)


def criar_meta(d):
    sql = "INSERT INTO metas (nome, valor_objetivo, valor_acumulado) VALUES (%s, %s, %s)"
    if not _mysql_disponivel():
        sql = "INSERT INTO metas (nome, valor_objetivo, valor_acumulado) VALUES (?, ?, ?)"
    _executar(sql, (d["nome"], d["valor_objetivo"], d["valor_acumulado"]))


def atualizar_meta(id_, d):
    sql = "UPDATE metas SET nome=%s, valor_objetivo=%s, valor_acumulado=%s WHERE id=%s"
    if not _mysql_disponivel():
        sql = "UPDATE metas SET nome=?, valor_objetivo=?, valor_acumulado=? WHERE id=?"
    _executar(sql, (d["nome"], d["valor_objetivo"], d["valor_acumulado"], id_))


def somar_meta(id_, valor):
    sql = "UPDATE metas SET valor_acumulado = valor_acumulado + %s WHERE id = %s"
    if not _mysql_disponivel():
        sql = "UPDATE metas SET valor_acumulado = valor_acumulado + ? WHERE id = ?"
    _executar(sql, (valor, id_))


def excluir_meta(id_):
    sql = "DELETE FROM metas WHERE id = %s"
    if not _mysql_disponivel():
        sql = "DELETE FROM metas WHERE id = ?"
    _executar(sql, (id_,))

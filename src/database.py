"""Database access for Finora Budget, with MySQL and local SQLite support."""
import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal

import mysql.connector

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
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


def _placeholder():
    return "%s" if _mysql_disponivel() else "?"


def _normalizar_parametro(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, date):
        return valor.isoformat()
    return valor


def _normalizar_parametros(params):
    return tuple(_normalizar_parametro(p) for p in params)


def init_db():
    """Create tables and add ownership columns without claiming legacy records."""
    if _mysql_disponivel():
        import mysql.connector

        con = conectar()
        try:
            cur = con.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    email VARCHAR(254) NOT NULL,
                    senha_hash VARCHAR(255) NOT NULL,
                    nome VARCHAR(80) NULL,
                    foto_perfil VARCHAR(100) NULL,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_usuarios_email (email)
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS movimentacoes (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    descricao VARCHAR(120) NOT NULL,
                    valor DECIMAL(12,2) NOT NULL,
                    tipo ENUM('receita','despesa') NOT NULL,
                    categoria VARCHAR(40) NOT NULL,
                    `data` DATE NOT NULL,
                    user_id INT UNSIGNED NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT chk_mov_valor CHECK (valor > 0),
                    INDEX idx_mov_data (`data`),
                    INDEX idx_mov_tipo (tipo),
                    INDEX idx_mov_usuario_data (user_id, `data`),
                    CONSTRAINT fk_movimentacoes_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metas (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    nome VARCHAR(100) NOT NULL,
                    valor_objetivo DECIMAL(12,2) NOT NULL,
                    valor_acumulado DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                    acompanhar_saldo TINYINT(1) NOT NULL DEFAULT 0,
                    user_id INT UNSIGNED NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT chk_meta_objetivo CHECK (valor_objetivo > 0),
                    CONSTRAINT chk_meta_acumulado CHECK (valor_acumulado >= 0),
                    INDEX idx_metas_usuario (user_id),
                    CONSTRAINT fk_metas_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS investimentos (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id INT UNSIGNED NOT NULL,
                    produto VARCHAR(40) NOT NULL,
                    instituicao VARCHAR(100) NOT NULL,
                    valor_inicial DECIMAL(12,2) NOT NULL,
                    saldo_atual DECIMAL(12,2) NOT NULL,
                    indexador VARCHAR(20) NOT NULL,
                    taxa_anual DECIMAL(7,3) NULL,
                    data_aplicacao DATE NOT NULL,
                    vencimento DATE NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT chk_investimento_valor CHECK (valor_inicial > 0),
                    CONSTRAINT chk_investimento_saldo CHECK (saldo_atual >= 0),
                    INDEX idx_investimentos_usuario_data (user_id, data_aplicacao),
                    CONSTRAINT fk_investimentos_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS resgates_investimentos (
                    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                    investimento_id INT UNSIGNED NOT NULL,
                    user_id INT UNSIGNED NOT NULL,
                    valor DECIMAL(12,2) NOT NULL,
                    data_resgate DATE NOT NULL,
                    PRIMARY KEY (id),
                    INDEX idx_resgates_usuario_data (user_id, data_resgate),
                    CONSTRAINT fk_resgates_investimento FOREIGN KEY (investimento_id) REFERENCES investimentos(id),
                    CONSTRAINT fk_resgates_usuario FOREIGN KEY (user_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB
                """
            )

            cur.execute("SHOW COLUMNS FROM usuarios LIKE 'nome'")
            if cur.fetchone() is None:
                cur.execute("ALTER TABLE usuarios ADD COLUMN nome VARCHAR(80) NULL")
            cur.execute("SHOW COLUMNS FROM usuarios LIKE 'foto_perfil'")
            if cur.fetchone() is None:
                cur.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil VARCHAR(100) NULL")

            # Upgrade databases created before ownership was introduced.
            for table in ("movimentacoes", "metas"):
                cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE 'user_id'")
                if cur.fetchone() is None:
                    cur.execute(f"ALTER TABLE `{table}` ADD COLUMN user_id INT UNSIGNED NULL")
                    cur.execute(f"ALTER TABLE `{table}` ADD INDEX idx_{table}_usuario (user_id)")
                    cur.execute(
                        f"ALTER TABLE `{table}` ADD CONSTRAINT fk_{table}_usuario "
                        "FOREIGN KEY (user_id) REFERENCES usuarios(id)"
                    )
            cur.execute("SHOW COLUMNS FROM metas LIKE 'acompanhar_saldo'")
            if cur.fetchone() is None:
                cur.execute(
                    "ALTER TABLE metas ADD COLUMN acompanhar_saldo TINYINT(1) NOT NULL DEFAULT 0"
                )
        finally:
            con.close()
        return

    con = sqlite3.connect(SQLITE_DB_PATH)
    try:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                senha_hash TEXT NOT NULL,
                nome TEXT,
                foto_perfil TEXT
            )
            """
        )
        user_columns = {row[1] for row in cur.execute("PRAGMA table_info(usuarios)")}
        if "nome" not in user_columns:
            cur.execute("ALTER TABLE usuarios ADD COLUMN nome TEXT")
        if "foto_perfil" not in user_columns:
            cur.execute("ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS movimentacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL CHECK(valor > 0),
                tipo TEXT NOT NULL,
                categoria TEXT NOT NULL,
                data TEXT NOT NULL,
                user_id INTEGER REFERENCES usuarios(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                valor_objetivo REAL NOT NULL CHECK(valor_objetivo > 0),
                valor_acumulado REAL NOT NULL DEFAULT 0 CHECK(valor_acumulado >= 0),
                acompanhar_saldo INTEGER NOT NULL DEFAULT 0,
                user_id INTEGER REFERENCES usuarios(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS investimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES usuarios(id),
                produto TEXT NOT NULL,
                instituicao TEXT NOT NULL,
                valor_inicial REAL NOT NULL CHECK(valor_inicial > 0),
                saldo_atual REAL NOT NULL CHECK(saldo_atual >= 0),
                indexador TEXT NOT NULL,
                taxa_anual REAL,
                data_aplicacao TEXT NOT NULL,
                vencimento TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS resgates_investimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                investimento_id INTEGER NOT NULL REFERENCES investimentos(id),
                user_id INTEGER NOT NULL REFERENCES usuarios(id),
                valor REAL NOT NULL CHECK(valor > 0),
                data_resgate TEXT NOT NULL
            )
            """
        )
        for table in ("movimentacoes", "metas"):
            columns = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in columns:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES usuarios(id)")
        meta_columns = {row[1] for row in cur.execute("PRAGMA table_info(metas)")}
        if "acompanhar_saldo" not in meta_columns:
            cur.execute("ALTER TABLE metas ADD COLUMN acompanhar_saldo INTEGER NOT NULL DEFAULT 0")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mov_usuario_data ON movimentacoes(user_id, data)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_metas_usuario ON metas(user_id)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_investimentos_usuario_data "
            "ON investimentos(user_id, data_aplicacao)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_resgates_usuario_data "
            "ON resgates_investimentos(user_id, data_resgate)"
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
            return [_normalizar_linha(dict(row)) for row in rows]
        return rows
    finally:
        con.close()


def _normalizar_linha(linha):
    for campo in ("data", "data_aplicacao", "vencimento"):
        if isinstance(linha.get(campo), str):
            linha[campo] = date.fromisoformat(linha[campo])
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


def criar_usuario(email, senha_hash):
    """Create an account. Return None only for a duplicate email."""
    try:
        return _executar(
            f"INSERT INTO usuarios (email, senha_hash) VALUES ({_placeholder()}, {_placeholder()})",
            (email, senha_hash),
        )
    except sqlite3.IntegrityError:
        return None
    except mysql.connector.IntegrityError as exc:
        if exc.errno == 1062:
            return None
        raise


def obter_usuario_por_email(email):
    return _consultar(
        f"SELECT id, email, senha_hash, nome FROM usuarios WHERE email = {_placeholder()}",
        (email,),
        um=True,
    )


def obter_usuario(id_):
    return _consultar(
        f"SELECT id, email, nome, foto_perfil FROM usuarios WHERE id = {_placeholder()}",
        (id_,),
        um=True,
    )


def atualizar_nome_usuario(user_id, nome):
    _executar(
        f"UPDATE usuarios SET nome = {_placeholder()} WHERE id = {_placeholder()}",
        (nome, user_id),
    )


def atualizar_perfil(user_id, nome, foto_perfil):
    _executar(
        f"UPDATE usuarios SET nome = {_placeholder()}, foto_perfil = {_placeholder()} "
        f"WHERE id = {_placeholder()}",
        (nome, foto_perfil, user_id),
    )


def contar_movimentacoes(user_id):
    row = _consultar(
        f"SELECT COUNT(*) AS total FROM movimentacoes WHERE user_id = {_placeholder()}",
        (user_id,),
        um=True,
    )
    return row["total"]


def _filtro(mes=None, tipo=None, user_id=None):
    where = [f"user_id = {_placeholder()}"]
    params = [user_id]
    if mes:
        inicio = datetime.strptime(mes, "%Y-%m").date()
        proximo_mes = date(
            inicio.year + (inicio.month == 12),
            1 if inicio.month == 12 else inicio.month + 1,
            1,
        )
        where.append(f"`data` >= {_placeholder()} AND `data` < {_placeholder()}")
        params.extend((inicio, proximo_mes))
    if tipo:
        where.append(f"tipo = {_placeholder()}")
        params.append(tipo)
    return " WHERE " + " AND ".join(where), params


# ---------- Movimentações ----------
def listar_movimentacoes(user_id, mes=None, tipo=None, limite=None):
    where, params = _filtro(mes, tipo, user_id)
    sql = "SELECT id, descricao, valor, tipo, categoria, `data` FROM movimentacoes" + where
    sql += " ORDER BY `data` DESC, id DESC"
    if limite:
        sql += f" LIMIT {_placeholder()}"
        params.append(int(limite))
    return _consultar(sql, params)


def obter_movimentacao(user_id, id_):
    return _consultar(
        f"SELECT id, descricao, valor, tipo, categoria, `data` FROM movimentacoes "
        f"WHERE id = {_placeholder()} AND user_id = {_placeholder()}",
        (id_, user_id),
        um=True,
    )


def criar_movimentacao(user_id, dados):
    p = _placeholder()
    _executar(
        "INSERT INTO movimentacoes (descricao, valor, tipo, categoria, `data`, user_id) "
        f"VALUES ({p}, {p}, {p}, {p}, {p}, {p})",
        (dados["descricao"], dados["valor"], dados["tipo"], dados["categoria"], dados["data"], user_id),
    )


def atualizar_movimentacao(user_id, id_, dados):
    p = _placeholder()
    _executar(
        "UPDATE movimentacoes SET descricao=%s, valor=%s, tipo=%s, categoria=%s, "
        "`data`=%s WHERE id=%s AND user_id=%s".replace("%s", p),
        (dados["descricao"], dados["valor"], dados["tipo"], dados["categoria"], dados["data"], id_, user_id),
    )


def excluir_movimentacao(user_id, id_):
    p = _placeholder()
    _executar(f"DELETE FROM movimentacoes WHERE id = {p} AND user_id = {p}", (id_, user_id))


def totais(user_id, mes=None):
    where, params = _filtro(mes, user_id=user_id)
    rows = _consultar(
        "SELECT tipo, SUM(valor) AS total FROM movimentacoes" + where + " GROUP BY tipo",
        params,
    )
    totals = {row["tipo"]: row["total"] for row in rows}
    return totals.get("receita", 0), totals.get("despesa", 0)


def eventos_saldo(user_id, fim):
    p = _placeholder()
    sql = (
        "SELECT `data`, SUM(delta) AS delta FROM ("
        f"SELECT `data`, CASE WHEN tipo = 'receita' THEN valor ELSE -valor END AS delta "
        f"FROM movimentacoes WHERE user_id = {p} AND `data` <= {p} "
        "UNION ALL "
        f"SELECT data_aplicacao AS `data`, -valor_inicial AS delta FROM investimentos "
        f"WHERE user_id = {p} AND data_aplicacao <= {p} "
        "UNION ALL "
        f"SELECT data_resgate AS `data`, valor AS delta FROM resgates_investimentos "
        f"WHERE user_id = {p} AND data_resgate <= {p}"
        ") eventos GROUP BY `data` ORDER BY `data`"
    )
    return _consultar(
        sql,
        (user_id, fim, user_id, fim, user_id, fim),
    )


def despesas_por_categoria(user_id, mes=None):
    where, params = _filtro(mes, "despesa", user_id)
    sql = (
        "SELECT categoria, SUM(valor) AS total FROM movimentacoes"
        + where
        + " GROUP BY categoria ORDER BY total DESC"
    )
    return _consultar(sql, params)


def saldo_investido(user_id):
    row = _consultar(
        f"SELECT COALESCE(SUM(saldo_atual), 0) AS total FROM investimentos "
        f"WHERE user_id = {_placeholder()}",
        (user_id,),
        um=True,
    )
    return row["total"] if row else 0


def investimentos_aplicados_no_mes(user_id, mes):
    inicio = datetime.strptime(mes, "%Y-%m").date()
    proximo_mes = date(
        inicio.year + (inicio.month == 12),
        1 if inicio.month == 12 else inicio.month + 1,
        1,
    )
    row = _consultar(
        f"SELECT COALESCE(SUM(valor_inicial), 0) AS total FROM investimentos "
        f"WHERE user_id = {_placeholder()} AND data_aplicacao >= {_placeholder()} "
        f"AND data_aplicacao < {_placeholder()}",
        (user_id, inicio, proximo_mes),
        um=True,
    )
    return row["total"] if row else 0


def investimentos_resgatados_no_mes(user_id, mes):
    inicio = datetime.strptime(mes, "%Y-%m").date()
    proximo_mes = date(
        inicio.year + (inicio.month == 12),
        1 if inicio.month == 12 else inicio.month + 1,
        1,
    )
    row = _consultar(
        f"SELECT COALESCE(SUM(valor), 0) AS total FROM resgates_investimentos "
        f"WHERE user_id = {_placeholder()} AND data_resgate >= {_placeholder()} "
        f"AND data_resgate < {_placeholder()}",
        (user_id, inicio, proximo_mes),
        um=True,
    )
    return row["total"] if row else 0


def listar_investimentos(user_id):
    return _consultar(
        f"SELECT id, produto, instituicao, valor_inicial, saldo_atual, indexador, "
        f"taxa_anual, data_aplicacao, vencimento FROM investimentos "
        f"WHERE user_id = {_placeholder()} ORDER BY data_aplicacao DESC, id DESC",
        (user_id,),
    )


def criar_investimento(user_id, dados):
    p = _placeholder()
    _executar(
        "INSERT INTO investimentos "
        "(user_id, produto, instituicao, valor_inicial, saldo_atual, indexador, "
        "taxa_anual, data_aplicacao, vencimento) "
        f"VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})",
        (
            user_id, dados["produto"], dados["instituicao"], dados["valor"],
            dados["valor"], dados["indexador"], dados["taxa_anual"],
            dados["data_aplicacao"], dados["vencimento"],
        ),
    )


def resgatar_investimento(user_id, id_, valor):
    p = _placeholder()
    con = conectar()
    try:
        cur = con.cursor()
        params = _normalizar_parametros((valor, id_, user_id, valor)) \
            if isinstance(con, sqlite3.Connection) else (valor, id_, user_id, valor)
        cur.execute(
            f"UPDATE investimentos SET saldo_atual = saldo_atual - {p} "
            f"WHERE id = {p} AND user_id = {p} AND saldo_atual >= {p}",
            params,
        )
        if cur.rowcount == 0:
            con.rollback()
            return False
        cur.execute(
            f"INSERT INTO resgates_investimentos "
            f"(investimento_id, user_id, valor, data_resgate) VALUES ({p}, {p}, {p}, {p})",
            _normalizar_parametros((id_, user_id, valor, date.today()))
            if isinstance(con, sqlite3.Connection)
            else (id_, user_id, valor, date.today()),
        )
        con.commit()
        return True
    finally:
        con.close()


# ---------- Metas ----------
def listar_metas(user_id):
    return _consultar(
        f"SELECT id, nome, valor_objetivo, valor_acumulado, acompanhar_saldo FROM metas "
        f"WHERE user_id = {_placeholder()} ORDER BY id DESC",
        (user_id,),
    )


def obter_meta(user_id, id_):
    return _consultar(
        f"SELECT id, nome, valor_objetivo, valor_acumulado, acompanhar_saldo FROM metas "
        f"WHERE id = {_placeholder()} AND user_id = {_placeholder()}",
        (id_, user_id),
        um=True,
    )


def criar_meta(user_id, dados):
    if dados.get("acompanhar_saldo") and meta_que_acompanha_saldo(user_id):
        raise ValueError("Já existe uma meta acompanhando o saldo disponível.")
    p = _placeholder()
    _executar(
        f"INSERT INTO metas (nome, valor_objetivo, valor_acumulado, acompanhar_saldo, user_id) "
        f"VALUES ({p}, {p}, {p}, {p}, {p})",
        (
            dados["nome"], dados["valor_objetivo"], dados["valor_acumulado"],
            int(bool(dados.get("acompanhar_saldo"))), user_id,
        ),
    )


def atualizar_meta(user_id, id_, dados):
    p = _placeholder()
    if dados.get("acompanhar_saldo") and meta_que_acompanha_saldo(user_id, id_):
        raise ValueError("Já existe uma meta acompanhando o saldo disponível.")
    _executar(
        "UPDATE metas SET nome=%s, valor_objetivo=%s, valor_acumulado=%s, acompanhar_saldo=%s "
        "WHERE id=%s AND user_id=%s".replace("%s", p),
        (
            dados["nome"], dados["valor_objetivo"], dados["valor_acumulado"],
            int(bool(dados.get("acompanhar_saldo"))), id_, user_id,
        ),
    )


def meta_que_acompanha_saldo(user_id, excluir_id=None):
    excluir = f" AND id != {_placeholder()}" if excluir_id is not None else ""
    params = (user_id, excluir_id) if excluir_id is not None else (user_id,)
    return _consultar(
        f"SELECT id FROM metas WHERE user_id = {_placeholder()} "
        f"AND acompanhar_saldo = 1{excluir} LIMIT 1",
        params,
        um=True,
    )


def somar_meta(user_id, id_, valor):
    p = _placeholder()
    _executar(
        f"UPDATE metas SET valor_acumulado = valor_acumulado + {p} "
        f"WHERE id = {p} AND user_id = {p}",
        (valor, id_, user_id),
    )


def excluir_meta(user_id, id_):
    p = _placeholder()
    _executar(f"DELETE FROM metas WHERE id = {p} AND user_id = {p}", (id_, user_id))

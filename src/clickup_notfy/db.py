import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS eventos_processados (
    id TEXT PRIMARY KEY,
    tipo_evento TEXT NOT NULL,
    task_id TEXT,
    payload_bruto TEXT NOT NULL,
    recebido_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mapeamentos_email (
    clickup_user_id INTEGER PRIMARY KEY,
    clickup_email TEXT NOT NULL,
    official_email TEXT NOT NULL,
    nome TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def conectar(database_path: str) -> sqlite3.Connection:
    conexao = sqlite3.connect(database_path)
    conexao.row_factory = sqlite3.Row
    return conexao


def inicializar_schema(conexao: sqlite3.Connection) -> None:
    conexao.executescript(SCHEMA)
    conexao.commit()

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

CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento_id TEXT NOT NULL,
    task_id TEXT,
    destinatario_email TEXT NOT NULL,
    tipo_evento TEXT NOT NULL,
    assunto TEXT NOT NULL,
    corpo TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    tentativas INTEGER NOT NULL DEFAULT 0,
    enviado_em TEXT,
    aberto INTEGER NOT NULL DEFAULT 0,
    aberto_em TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notificacoes_status ON notificacoes_enviadas (status);
CREATE INDEX IF NOT EXISTS idx_notificacoes_created_at ON notificacoes_enviadas (created_at);
CREATE INDEX IF NOT EXISTS idx_notificacoes_dedup ON notificacoes_enviadas (task_id, tipo_evento, destinatario_email);

CREATE TABLE IF NOT EXISTS alertas_operacionais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    enviado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alertas_tipo_enviado_em ON alertas_operacionais (tipo, enviado_em);
"""


def conectar(database_path: str) -> sqlite3.Connection:
    conexao = sqlite3.connect(database_path)
    conexao.row_factory = sqlite3.Row
    return conexao


def inicializar_schema(conexao: sqlite3.Connection) -> None:
    conexao.executescript(SCHEMA)
    conexao.commit()

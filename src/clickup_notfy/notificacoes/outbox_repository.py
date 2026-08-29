import sqlite3


def criar_pendente(
    conexao: sqlite3.Connection, evento_id: str, destinatario_email: str, tipo_evento: str
) -> int:
    cursor = conexao.execute(
        """
        INSERT INTO notificacoes_enviadas (evento_id, destinatario_email, tipo_evento)
        VALUES (?, ?, ?)
        """,
        (evento_id, destinatario_email, tipo_evento),
    )
    conexao.commit()
    return cursor.lastrowid


def registrar_resultado_envio(conexao: sqlite3.Connection, notificacao_id: int, sucesso: bool) -> None:
    if sucesso:
        conexao.execute(
            """
            UPDATE notificacoes_enviadas
            SET status = 'enviado', enviado_em = datetime('now'), tentativas = tentativas + 1
            WHERE id = ?
            """,
            (notificacao_id,),
        )
    else:
        conexao.execute(
            "UPDATE notificacoes_enviadas SET tentativas = tentativas + 1 WHERE id = ?",
            (notificacao_id,),
        )
    conexao.commit()


def listar_pendentes(conexao: sqlite3.Connection) -> list[dict]:
    cursor = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE status = 'pendente' ORDER BY created_at ASC"
    )
    return [dict(linha) for linha in cursor.fetchall()]

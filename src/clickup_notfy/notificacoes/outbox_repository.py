import sqlite3

JANELA_DUPLICATA_MINUTOS = 5


def criar_pendente(
    conexao: sqlite3.Connection,
    evento_id: str,
    task_id: str,
    destinatario_email: str,
    tipo_evento: str,
    assunto: str,
    corpo: str,
) -> int:
    cursor = conexao.execute(
        """
        INSERT INTO notificacoes_enviadas (evento_id, task_id, destinatario_email, tipo_evento, assunto, corpo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (evento_id, task_id, destinatario_email, tipo_evento, assunto, corpo),
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


def ja_enviada_recentemente(
    conexao: sqlite3.Connection,
    task_id: str,
    tipo_evento: str,
    destinatario_email: str,
    corpo: str,
    janela_minutos: int = JANELA_DUPLICATA_MINUTOS,
) -> bool:
    """Detecta notificacao com conteudo identico ja enviada com sucesso pro
    mesmo chamado/tipo/destinatario nos ultimos minutos.

    Existe pra cobrir casos como o ClickUp emitindo dois history_items
    diferentes (IDs distintos, entao o dedup por evento_id nao pega) pra
    uma unica acao real do usuario (ex: 2 eventos "taskCreated" pra 1
    criacao de chamado, poucos segundos um do outro). Compara o corpo
    renderizado (nao so o tipo) pra nao suprimir duas mudancas de status
    reais e diferentes que aconteçam por acaso perto uma da outra.
    """
    cursor = conexao.execute(
        """
        SELECT 1 FROM notificacoes_enviadas
        WHERE task_id = ?
          AND tipo_evento = ?
          AND destinatario_email = ?
          AND corpo = ?
          AND status = 'enviado'
          AND created_at >= datetime('now', ?)
        LIMIT 1
        """,
        (task_id, tipo_evento, destinatario_email, corpo, f"-{janela_minutos} minutes"),
    )
    return cursor.fetchone() is not None

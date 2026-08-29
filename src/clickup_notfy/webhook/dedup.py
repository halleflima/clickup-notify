import sqlite3


def evento_ja_processado(conexao: sqlite3.Connection, evento_id: str) -> bool:
    cursor = conexao.execute(
        "SELECT 1 FROM eventos_processados WHERE id = ?", (evento_id,)
    )
    return cursor.fetchone() is not None


def registrar_evento(
    conexao: sqlite3.Connection,
    evento_id: str,
    tipo_evento: str,
    task_id: str | None,
    payload_bruto: str,
) -> None:
    conexao.execute(
        """
        INSERT INTO eventos_processados (id, tipo_evento, task_id, payload_bruto)
        VALUES (?, ?, ?, ?)
        """,
        (evento_id, tipo_evento, task_id, payload_bruto),
    )
    conexao.commit()

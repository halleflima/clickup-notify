import sqlite3


def houve_alerta_recente(conexao: sqlite3.Connection, tipo: str, janela_minutos: int) -> bool:
    cursor = conexao.execute(
        """
        SELECT 1 FROM alertas_operacionais
        WHERE tipo = ? AND enviado_em >= datetime('now', ?)
        LIMIT 1
        """,
        (tipo, f'-{janela_minutos} minutes'),
    )
    return cursor.fetchone() is not None


def registrar_alerta(conexao: sqlite3.Connection, tipo: str) -> None:
    conexao.execute('INSERT INTO alertas_operacionais (tipo) VALUES (?)', (tipo,))
    conexao.commit()

import sqlite3

CAMPOS_ATUALIZAVEIS = {"clickup_email", "official_email", "nome", "ativo"}


def _serializar(linha: sqlite3.Row) -> dict:
    dado = dict(linha)
    dado["ativo"] = bool(dado["ativo"])
    return dado


def criar(
    conexao: sqlite3.Connection,
    clickup_user_id: int,
    clickup_email: str,
    official_email: str,
    nome: str,
) -> None:
    conexao.execute(
        """
        INSERT INTO mapeamentos_email (clickup_user_id, clickup_email, official_email, nome)
        VALUES (?, ?, ?, ?)
        """,
        (clickup_user_id, clickup_email, official_email, nome),
    )
    conexao.commit()


def listar(conexao: sqlite3.Connection, apenas_ativos: bool | None = None) -> list[dict]:
    if apenas_ativos is None:
        cursor = conexao.execute("SELECT * FROM mapeamentos_email ORDER BY nome")
    else:
        cursor = conexao.execute(
            "SELECT * FROM mapeamentos_email WHERE ativo = ? ORDER BY nome",
            (1 if apenas_ativos else 0,),
        )
    return [_serializar(linha) for linha in cursor.fetchall()]


def buscar_por_id(conexao: sqlite3.Connection, clickup_user_id: int) -> dict | None:
    cursor = conexao.execute(
        "SELECT * FROM mapeamentos_email WHERE clickup_user_id = ?", (clickup_user_id,)
    )
    linha = cursor.fetchone()
    return _serializar(linha) if linha else None


def atualizar(conexao: sqlite3.Connection, clickup_user_id: int, campos: dict) -> bool:
    campos_validos = {chave: valor for chave, valor in campos.items() if chave in CAMPOS_ATUALIZAVEIS}
    if not campos_validos:
        return False

    if "ativo" in campos_validos:
        campos_validos["ativo"] = 1 if campos_validos["ativo"] else 0

    atribuicoes = ", ".join(f"{campo} = ?" for campo in campos_validos)
    valores = [*campos_validos.values(), clickup_user_id]

    cursor = conexao.execute(
        f"UPDATE mapeamentos_email SET {atribuicoes}, updated_at = datetime('now') "
        "WHERE clickup_user_id = ?",
        valores,
    )
    conexao.commit()
    return cursor.rowcount > 0

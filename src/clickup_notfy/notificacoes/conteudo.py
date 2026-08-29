"""Construcao do assunto/corpo do email, conforme ADR-0002.

Conteudo propositalmente minimalista - o objetivo e levar o destinatario
ate o ClickUp, nao substituir a ferramenta.
"""

OBSERVACOES_POR_STATUS = {
    "reanálise": "Este chamado precisa ser analisado, por favor acesse o ClickUp.",
}

_TITULOS_POR_EVENTO = {
    "taskCreated": "Novo chamado criado: {task_id}",
    "taskCommentPosted": "Novo comentário no chamado {task_id}",
    "taskStatusUpdated": "Chamado {task_id} mudou de status",
    "taskAssigneeUpdated": "Atualização de responsável no chamado {task_id}",
}


def montar_assunto(tipo_evento: str, task_id: str) -> str:
    modelo = _TITULOS_POR_EVENTO.get(tipo_evento, "Atualização no chamado {task_id}")
    return modelo.format(task_id=task_id)


def montar_corpo(
    tipo_evento: str,
    task_id: str,
    destinatario: dict,
    before: str | None = None,
    after: str | None = None,
) -> str:
    if tipo_evento == "taskCreated":
        return f"O chamado {task_id} foi criado."

    if tipo_evento == "taskCommentPosted":
        return (
            f"Novo comentário adicionado no chamado {task_id}. "
            "Acesse o ClickUp para visualizar e gerenciar o chamado."
        )

    if tipo_evento == "taskStatusUpdated":
        corpo = f"O chamado {task_id} foi alterado de {before} para {after}."
        observacao = OBSERVACOES_POR_STATUS.get((after or "").strip().casefold())
        if observacao:
            corpo += f"\n\n{observacao}"
        return corpo

    if tipo_evento == "taskAssigneeUpdated":
        if destinatario.get("papel") == "atribuido":
            return f"Você foi atribuído ao chamado {task_id}."
        return f"Você foi desvinculado do chamado {task_id}."

    return f"Houve uma atualização no chamado {task_id}."

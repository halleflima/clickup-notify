"""Regras de destinatario por tipo de evento, conforme ADR-0002.

Cada funcao recebe o estado ja resolvido (responsavel/solicitante atuais,
vindos da API do ClickUp, ou o antes/depois do proprio evento) e devolve
quem deve ser notificado. Construcao de conteudo de email e envio ficam
para uma etapa posterior (outbox).
"""

EVENTOS_SUPORTADOS = {
    "taskCreated",
    "taskStatusUpdated",
    "taskCommentPosted",
    "taskAssigneeUpdated",
}


def resolver_destinatarios_criacao(
    solicitantes_ids: list[int], responsaveis_ids: list[int]
) -> list[dict]:
    """Notifica TODOS os solicitantes (um chamado pode ter mais de um, ver
    ADR-0012), nao so o primeiro."""
    destinatarios = [
        {"clickup_user_id": sid, "papel": "solicitante"} for sid in solicitantes_ids
    ]
    destinatarios += [
        {"clickup_user_id": rid, "papel": "responsavel"} for rid in responsaveis_ids
    ]
    return destinatarios


def resolver_destinatarios_envolvidos(
    autor_id: int, solicitantes_ids: list[int], responsaveis_ids: list[int]
) -> list[dict]:
    """Usado por comentario e mudanca de status: notifica responsaveis e
    todos os solicitantes, exceto quem executou a propria acao."""
    envolvidos_ids = set(responsaveis_ids)
    envolvidos_ids.update(solicitantes_ids)
    envolvidos_ids.discard(autor_id)

    return [{"clickup_user_id": uid, "papel": "envolvido"} for uid in envolvidos_ids]


def resolver_destinatarios_atribuicao(
    autor_id: int, responsaveis_ids_antes: list[int], responsaveis_ids_depois: list[int]
) -> list[dict]:
    """Diff de responsaveis antes/depois de um taskAssigneeUpdated."""
    antes = set(responsaveis_ids_antes)
    depois = set(responsaveis_ids_depois)

    adicionados = (depois - antes) - {autor_id}
    removidos = (antes - depois) - {autor_id}

    destinatarios = [{"clickup_user_id": uid, "papel": "atribuido"} for uid in adicionados]
    destinatarios += [{"clickup_user_id": uid, "papel": "removido"} for uid in removidos]
    return destinatarios

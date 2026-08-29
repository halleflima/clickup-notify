"""Regras de destinatario por tipo de evento, conforme ADR-0002.

Cada funcao recebe o estado ja resolvido (responsavel/solicitante atuais,
vindos da API do ClickUp, ou o antes/depois do proprio evento) e devolve
quem deve ser notificado. Construcao de conteudo de email e envio ficam
para uma etapa posterior (outbox).
"""


def resolver_destinatarios_criacao(
    solicitante_id: int | None, responsaveis_ids: list[int]
) -> list[dict]:
    destinatarios = []
    if solicitante_id is not None:
        destinatarios.append({"clickup_user_id": solicitante_id, "papel": "solicitante"})
    destinatarios += [
        {"clickup_user_id": rid, "papel": "responsavel"} for rid in responsaveis_ids
    ]
    return destinatarios


def resolver_destinatarios_envolvidos(
    autor_id: int, solicitante_id: int | None, responsaveis_ids: list[int]
) -> list[dict]:
    """Usado por comentario e mudanca de status: notifica responsaveis e
    solicitante, exceto quem executou a propria acao."""
    envolvidos_ids = set(responsaveis_ids)
    if solicitante_id is not None:
        envolvidos_ids.add(solicitante_id)
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

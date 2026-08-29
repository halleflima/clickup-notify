from clickup_notfy import clickup_api
from clickup_notfy.mapeamentos import repository as mapeamentos_repository
from clickup_notfy.notificacoes import conteudo, email_sender, outbox_repository, regras


def _extrair_ids(valores) -> list[int]:
    return [valor["id"] if isinstance(valor, dict) else valor for valor in (valores or [])]


def resolver_destinatarios_do_evento(item: dict, config) -> list[dict]:
    tipo_evento = item["tipo_evento"]

    if tipo_evento == "taskAssigneeUpdated":
        return regras.resolver_destinatarios_atribuicao(
            autor_id=item["autor_id"],
            responsaveis_ids_antes=_extrair_ids(item["before"]),
            responsaveis_ids_depois=_extrair_ids(item["after"]),
        )

    tarefa = clickup_api.buscar_tarefa(item["task_id"], config["CLICKUP_API_TOKEN"])
    responsaveis_ids = clickup_api.extrair_responsaveis_ids(tarefa)
    solicitante_id = clickup_api.extrair_solicitante_id(tarefa)

    if tipo_evento == "taskCreated":
        return regras.resolver_destinatarios_criacao(solicitante_id, responsaveis_ids)

    return regras.resolver_destinatarios_envolvidos(item["autor_id"], solicitante_id, responsaveis_ids)


def _resolver_email_destino(conexao, clickup_user_id: int, config) -> str:
    mapeamento = mapeamentos_repository.buscar_por_id(conexao, clickup_user_id)
    if mapeamento and mapeamento["ativo"]:
        return mapeamento["official_email"]
    return config["FALLBACK_EMAIL"]


def processar_evento(conexao, item: dict, config) -> None:
    destinatarios = resolver_destinatarios_do_evento(item, config)

    for destinatario in destinatarios:
        email_destino = _resolver_email_destino(conexao, destinatario["clickup_user_id"], config)

        assunto = conteudo.montar_assunto(item["tipo_evento"], item["task_id"])
        corpo = conteudo.montar_corpo(
            item["tipo_evento"], item["task_id"], destinatario, item.get("before"), item.get("after")
        )

        notificacao_id = outbox_repository.criar_pendente(
            conexao, item["id"], email_destino, item["tipo_evento"]
        )
        sucesso = email_sender.tentar_enviar(config, email_destino, assunto, corpo)
        outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso)

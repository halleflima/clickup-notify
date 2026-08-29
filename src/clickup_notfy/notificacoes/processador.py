from clickup_notfy import clickup_api
from clickup_notfy.mapeamentos import repository as mapeamentos_repository
from clickup_notfy.notificacoes import conteudo, email_sender, outbox_repository, regras


def _extrair_pessoas(valores) -> list[dict]:
    pessoas = []
    for valor in valores or []:
        if isinstance(valor, dict):
            pessoas.append({"id": valor["id"], "email": valor.get("email"), "nome": valor.get("username")})
        else:
            pessoas.append({"id": valor, "email": None, "nome": None})
    return pessoas


def _mapa_pessoas(pessoas: list[dict]) -> dict[int, dict]:
    return {pessoa["id"]: pessoa for pessoa in pessoas}


def resolver_contexto_evento(item: dict, config) -> tuple[list[dict], dict[int, dict]]:
    """Resolve quem deve ser notificado e o que se sabe (email/nome) de cada um."""
    tipo_evento = item["tipo_evento"]

    if tipo_evento == "taskAssigneeUpdated":
        pessoas_antes = _extrair_pessoas(item["before"])
        pessoas_depois = _extrair_pessoas(item["after"])
        destinatarios = regras.resolver_destinatarios_atribuicao(
            autor_id=item["autor_id"],
            responsaveis_ids_antes=[p["id"] for p in pessoas_antes],
            responsaveis_ids_depois=[p["id"] for p in pessoas_depois],
        )
        return destinatarios, _mapa_pessoas(pessoas_antes + pessoas_depois)

    tarefa = clickup_api.buscar_tarefa(item["task_id"], config["CLICKUP_API_TOKEN"])
    responsaveis = clickup_api.extrair_responsaveis(tarefa)
    solicitante = clickup_api.extrair_solicitante(tarefa)
    responsaveis_ids = [r["id"] for r in responsaveis]
    solicitante_id = solicitante["id"] if solicitante else None

    pessoas_conhecidas = _mapa_pessoas(responsaveis + ([solicitante] if solicitante else []))

    if tipo_evento == "taskCreated":
        destinatarios = regras.resolver_destinatarios_criacao(solicitante_id, responsaveis_ids)
    else:
        destinatarios = regras.resolver_destinatarios_envolvidos(
            item["autor_id"], solicitante_id, responsaveis_ids
        )

    return destinatarios, pessoas_conhecidas


def _resolver_email_destino(conexao, clickup_user_id: int, pessoa_info: dict | None, config) -> str:
    mapeamento = mapeamentos_repository.buscar_por_id(conexao, clickup_user_id)
    if mapeamento:
        if mapeamento["ativo"]:
            return mapeamento["official_email"]
        return config["FALLBACK_EMAIL"]

    if pessoa_info and pessoa_info.get("email"):
        email_clickup = pessoa_info["email"]
        nome = pessoa_info.get("nome") or email_clickup
        mapeamentos_repository.criar(conexao, clickup_user_id, email_clickup, email_clickup, nome)
        return email_clickup

    return config["FALLBACK_EMAIL"]


def processar_evento(conexao, item: dict, config) -> None:
    destinatarios, pessoas_conhecidas = resolver_contexto_evento(item, config)

    for destinatario in destinatarios:
        pessoa_info = pessoas_conhecidas.get(destinatario["clickup_user_id"])
        email_destino = _resolver_email_destino(
            conexao, destinatario["clickup_user_id"], pessoa_info, config
        )

        assunto = conteudo.montar_assunto(item["tipo_evento"], item["task_id"])
        corpo = conteudo.montar_corpo(
            item["tipo_evento"], item["task_id"], destinatario, item.get("before"), item.get("after")
        )

        notificacao_id = outbox_repository.criar_pendente(
            conexao, item["id"], email_destino, item["tipo_evento"], assunto, corpo
        )
        sucesso = email_sender.tentar_enviar(config, email_destino, assunto, corpo)
        outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso)

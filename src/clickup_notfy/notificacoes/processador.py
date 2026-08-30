from clickup_notfy import clickup_api
from clickup_notfy.mapeamentos import repository as mapeamentos_repository
from clickup_notfy.notificacoes import conteudo, email_sender, outbox_repository, regras


def _extrair_pessoas(valores) -> list[dict]:
    """Normaliza before/after de taskAssigneeUpdated.

    Confirmado em producao: para uma unica pessoa adicionada/removida, o
    ClickUp manda um objeto unico (nao uma lista) - ex: {"id": 123, ...}.
    So vem como lista quando mais de uma pessoa muda de uma vez. Tratar so
    o caso lista quebra silenciosamente (itera as CHAVES do dict).
    """
    if valores is None:
        return []
    if isinstance(valores, dict):
        valores = [valores]

    pessoas = []
    for valor in valores:
        if isinstance(valor, dict):
            pessoas.append({"id": valor["id"], "email": valor.get("email"), "nome": valor.get("username")})
        else:
            pessoas.append({"id": valor, "email": None, "nome": None})
    return pessoas


def _mapa_pessoas(pessoas: list[dict]) -> dict[int, dict]:
    return {pessoa["id"]: pessoa for pessoa in pessoas}


def _resolver_contexto_atribuicao(item: dict) -> tuple[list[dict], dict[int, dict], str]:
    pessoas_antes = _extrair_pessoas(item["before"])
    pessoas_depois = _extrair_pessoas(item["after"])

    destinatarios = regras.resolver_destinatarios_atribuicao(
        autor_id=item["autor_id"],
        responsaveis_ids_antes=[pessoa["id"] for pessoa in pessoas_antes],
        responsaveis_ids_depois=[pessoa["id"] for pessoa in pessoas_depois],
    )
    # Este evento nao busca a tarefa na API (ver ADR-0002), entao nao temos
    # como saber o custom_id aqui - usa o id bruto do ClickUp mesmo.
    return destinatarios, _mapa_pessoas(pessoas_antes + pessoas_depois), item["task_id"]


def _resolver_contexto_via_tarefa(item: dict, config) -> tuple[list[dict], dict[int, dict], str]:
    tarefa = clickup_api.buscar_tarefa(item["task_id"], config["CLICKUP_API_TOKEN"])
    identificador_tarefa = tarefa.get("custom_id") or item["task_id"]
    responsaveis = clickup_api.extrair_responsaveis(tarefa)
    solicitante = clickup_api.extrair_solicitante(tarefa)
    responsaveis_ids = [responsavel["id"] for responsavel in responsaveis]
    solicitante_id = solicitante["id"] if solicitante else None
    pessoas_conhecidas = _mapa_pessoas(responsaveis + ([solicitante] if solicitante else []))

    if item["tipo_evento"] == "taskCreated":
        destinatarios = regras.resolver_destinatarios_criacao(solicitante_id, responsaveis_ids)
        return destinatarios, pessoas_conhecidas, identificador_tarefa

    destinatarios = regras.resolver_destinatarios_envolvidos(
        item["autor_id"], solicitante_id, responsaveis_ids
    )
    return destinatarios, pessoas_conhecidas, identificador_tarefa


def resolver_contexto_evento(item: dict, config) -> tuple[list[dict], dict[int, dict], str]:
    """Resolve quem deve ser notificado, o que se sabe (email/nome) de cada
    um, e o identificador de exibicao do chamado (custom_id tipo "DV-8165"
    quando disponivel, senao o id bruto do ClickUp).

    O webhook do ClickUp pode estar inscrito em "*" (todos os eventos) -
    qualquer tipo fora de EVENTOS_SUPORTADOS e ignorado aqui, sem chamar a
    API do ClickUp nem tentar montar notificacao pra algo que nao mapeamos.
    """
    if item["tipo_evento"] not in regras.EVENTOS_SUPORTADOS:
        return [], {}, item["task_id"]

    if item["tipo_evento"] == "taskAssigneeUpdated":
        return _resolver_contexto_atribuicao(item)
    return _resolver_contexto_via_tarefa(item, config)


def _garantir_mapeamento(conexao, clickup_user_id: int, pessoa_info: dict | None) -> None:
    """Cadastra o mapeamento se ainda nao existir, independente de a pessoa
    vir a ser notificada ou nao neste evento (ex: suprimida por ser a
    autora da propria acao). Objetivo: o time vai sendo conhecido aos
    poucos, mesmo em eventos que nao geram notificacao pra ninguem."""
    if mapeamentos_repository.buscar_por_id(conexao, clickup_user_id):
        return
    if not pessoa_info or not pessoa_info.get("email"):
        return

    email_clickup = pessoa_info["email"]
    nome = pessoa_info.get("nome") or email_clickup
    mapeamentos_repository.criar(conexao, clickup_user_id, email_clickup, email_clickup, nome)


def _resolver_email_destino(conexao, clickup_user_id: int, config) -> str:
    mapeamento = mapeamentos_repository.buscar_por_id(conexao, clickup_user_id)
    if mapeamento and mapeamento["ativo"]:
        return mapeamento["official_email"]
    return config["FALLBACK_EMAIL"]


def processar_evento(conexao, item: dict, config) -> None:
    destinatarios, pessoas_conhecidas, identificador_tarefa = resolver_contexto_evento(item, config)

    for clickup_user_id, pessoa_info in pessoas_conhecidas.items():
        _garantir_mapeamento(conexao, clickup_user_id, pessoa_info)

    for destinatario in destinatarios:
        email_destino = _resolver_email_destino(conexao, destinatario["clickup_user_id"], config)

        assunto = conteudo.montar_assunto(item["tipo_evento"], identificador_tarefa)
        corpo = conteudo.montar_corpo(
            item["tipo_evento"], identificador_tarefa, destinatario, item.get("before"), item.get("after")
        )

        notificacao_id = outbox_repository.criar_pendente(
            conexao, item["id"], email_destino, item["tipo_evento"], assunto, corpo
        )
        sucesso = email_sender.tentar_enviar(config, email_destino, assunto, corpo)
        outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso)

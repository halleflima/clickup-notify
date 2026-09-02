import logging

from clickup_notfy import clickup_api
from clickup_notfy.mapeamentos import repository as mapeamentos_repository
from clickup_notfy.notificacoes import conteudo, email_sender, outbox_repository, regras

logger = logging.getLogger(__name__)


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


def _nomes_ou(pessoas: list[dict], texto_vazio: str) -> str:
    nomes = [pessoa.get("nome") or pessoa.get("email") or "desconhecido" for pessoa in pessoas if pessoa]
    return ", ".join(nomes) if nomes else texto_vazio


def _metadados_da_tarefa(
    tarefa: dict, responsaveis: list[dict], solicitantes: list[dict], task_id_bruto: str
) -> dict:
    return {
        "identificador": tarefa.get("custom_id") or task_id_bruto,
        "titulo": clickup_api.extrair_nome_tarefa(tarefa),
        "prioridade": clickup_api.extrair_prioridade(tarefa),
        "descricao": clickup_api.extrair_descricao(tarefa),
        "status_atual": clickup_api.extrair_status_atual(tarefa),
        "responsavel_nome": _nomes_ou(responsaveis, "Não atribuído"),
        "solicitante_nome": _nomes_ou(solicitantes, "-"),
    }


def resolver_contexto_evento(item: dict, config) -> tuple[list[dict], dict[int, dict], dict]:
    """Resolve quem deve ser notificado, o que se sabe (email/nome) de cada
    um, e os metadados de exibicao do chamado (titulo, prioridade, status
    atual, etc - ver _metadados_da_tarefa).

    O webhook do ClickUp pode estar inscrito em "*" (todos os eventos) -
    qualquer tipo fora de EVENTOS_SUPORTADOS e ignorado aqui, sem chamar a
    API do ClickUp nem tentar montar notificacao pra algo que nao mapeamos.

    Busca a tarefa completa pros 4 eventos suportados (inclusive
    taskAssigneeUpdated, que antes nao buscava) - decisao revisada pra
    poder exibir titulo/status/prioridade tambem nesse tipo de evento.
    """
    if item["tipo_evento"] not in regras.EVENTOS_SUPORTADOS:
        return [], {}, {"identificador": item["task_id"]}

    tarefa = clickup_api.buscar_tarefa(item["task_id"], config["CLICKUP_API_TOKEN"])
    responsaveis = clickup_api.extrair_responsaveis(tarefa)
    solicitantes = clickup_api.extrair_solicitantes(tarefa)
    responsaveis_ids = [responsavel["id"] for responsavel in responsaveis]
    solicitantes_ids = [solicitante["id"] for solicitante in solicitantes]
    metadados = _metadados_da_tarefa(tarefa, responsaveis, solicitantes, item["task_id"])

    if item["tipo_evento"] == "taskAssigneeUpdated":
        pessoas_antes = _extrair_pessoas(item["before"])
        pessoas_depois = _extrair_pessoas(item["after"])
        destinatarios = regras.resolver_destinatarios_atribuicao(
            autor_id=item["autor_id"],
            responsaveis_ids_antes=[pessoa["id"] for pessoa in pessoas_antes],
            responsaveis_ids_depois=[pessoa["id"] for pessoa in pessoas_depois],
        )
        pessoas_conhecidas = _mapa_pessoas(pessoas_antes + pessoas_depois + responsaveis + solicitantes)
        return destinatarios, pessoas_conhecidas, metadados

    pessoas_conhecidas = _mapa_pessoas(responsaveis + solicitantes)

    if item["tipo_evento"] == "taskCreated":
        destinatarios = regras.resolver_destinatarios_criacao(solicitantes_ids, responsaveis_ids)
        return destinatarios, pessoas_conhecidas, metadados

    destinatarios = regras.resolver_destinatarios_envolvidos(
        item["autor_id"], solicitantes_ids, responsaveis_ids
    )
    return destinatarios, pessoas_conhecidas, metadados


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


def _resolver_nome_destinatario(conexao, clickup_user_id: int, pessoa_info: dict | None) -> str:
    mapeamento = mapeamentos_repository.buscar_por_id(conexao, clickup_user_id)
    if mapeamento and mapeamento["nome"]:
        return mapeamento["nome"]
    if pessoa_info and pessoa_info.get("nome"):
        return pessoa_info["nome"]
    return "colega"


def processar_evento(conexao, item: dict, config) -> None:
    destinatarios, pessoas_conhecidas, metadados = resolver_contexto_evento(item, config)

    for clickup_user_id, pessoa_info in pessoas_conhecidas.items():
        _garantir_mapeamento(conexao, clickup_user_id, pessoa_info)

    for destinatario in destinatarios:
        clickup_user_id = destinatario["clickup_user_id"]
        email_destino = _resolver_email_destino(conexao, clickup_user_id, config)
        pessoa_info = pessoas_conhecidas.get(clickup_user_id)
        nome_destinatario = _resolver_nome_destinatario(conexao, clickup_user_id, pessoa_info)

        assunto, corpo_html = conteudo.montar_email(item, destinatario, metadados, nome_destinatario)

        if outbox_repository.ja_enviada_recentemente(
            conexao, item["task_id"], item["tipo_evento"], email_destino, corpo_html
        ):
            logger.info(
                "Notificacao identica ja enviada recentemente pro chamado %s (tipo %s, destinatario %s) - ignorando duplicata",
                item["task_id"],
                item["tipo_evento"],
                email_destino,
            )
            continue

        notificacao_id = outbox_repository.criar_pendente(
            conexao, item["id"], item["task_id"], email_destino, item["tipo_evento"], assunto, corpo_html
        )
        sucesso = email_sender.tentar_enviar(config, email_destino, assunto, corpo_html)
        outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso)

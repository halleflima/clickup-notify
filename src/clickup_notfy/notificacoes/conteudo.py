"""Montagem do email de notificacao a partir do template HTML (ADR-0009).

Conteudo minimalista de proposito pra comentario (ADR-0002) - sem o texto
do comentario em si, so um aviso + link pro ClickUp.
"""

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

_DIR_TEMPLATES = Path(__file__).parent / "templates"
_AMBIENTE = Environment(
    loader=FileSystemLoader(str(_DIR_TEMPLATES)),
    autoescape=select_autoescape(["html", "jinja2"]),
)
_TEMPLATE = _AMBIENTE.get_template("email.html.jinja2")

COR_PADRAO = "#3E7CB1"
_CORES_POR_STATUS = {
    "encerrado": "#2f8f5b",
}

OBSERVACOES_POR_STATUS = {
    "reanálise": (
        "Este chamado está em reanálise, geralmente por falta de dados. "
        "Por favor, acesse o ClickUp para revisar as informações."
    ),
}

EMPRESA_SIGLA = "CMM"
EMPRESA_NOME = "CMM Sistemas de Informação"
EMPRESA_LOGO_URL = "https://cmmsistemas.com.br/wp-content/uploads/2022/06/logo-cmm.png"
NAO_ATRIBUIDO = "Não atribuído"


def _formatar_data(data_epoch_ms) -> str:
    try:
        momento = datetime.datetime.fromtimestamp(int(data_epoch_ms) / 1000)
    except (TypeError, ValueError):
        momento = datetime.datetime.now()
    return momento.strftime("%d/%m/%Y às %H:%M")


def _cor_por_status(status: str | None) -> str:
    if not status:
        return COR_PADRAO
    return _CORES_POR_STATUS.get(status.strip().casefold(), COR_PADRAO)


def _contexto_criacao(metadados: dict) -> dict:
    return {
        "evento_tipo": "Novo chamado",
        "evento_titulo": "Um novo chamado foi aberto",
        "evento_descricao": "O chamado abaixo foi criado com sucesso.",
        "alteracao_label": None,
        "alteracao_de": None,
        "alteracao_para": None,
        "texto_label": "Descrição do solicitante" if metadados["descricao"] else None,
        "texto_corpo": metadados["descricao"],
    }


def _contexto_comentario(identificador: str) -> dict:
    return {
        "evento_tipo": "Novo comentário",
        "evento_titulo": f"Novo comentário no chamado {identificador}",
        "evento_descricao": (
            "Um novo comentário foi adicionado ao chamado que você acompanha. "
            "Acesse o ClickUp para ver o conteúdo."
        ),
        "alteracao_label": None,
        "alteracao_de": None,
        "alteracao_para": None,
        "texto_label": None,
        "texto_corpo": None,
    }


def _contexto_status(identificador: str, status_antigo: str | None, status_novo: str | None) -> dict:
    observacao = OBSERVACOES_POR_STATUS.get((status_novo or "").strip().casefold())
    return {
        "evento_tipo": "Mudança de status",
        "evento_titulo": f"O status do chamado {identificador} foi alterado",
        "evento_descricao": f"O chamado saiu de {status_antigo} e agora está {status_novo}.",
        "alteracao_label": "Status",
        "alteracao_de": status_antigo,
        "alteracao_para": status_novo,
        "texto_label": "Observação" if observacao else None,
        "texto_corpo": observacao,
    }


def _contexto_atribuicao(papel: str, nome_destinatario: str) -> dict:
    if papel == "atribuido":
        return {
            "evento_tipo": "Mudança de responsável",
            "evento_titulo": "Uma tarefa foi vinculada à sua responsabilidade",
            "evento_descricao": (
                "Você é o novo responsável por este chamado. Confira os detalhes "
                "abaixo e dê o primeiro retorno ao solicitante."
            ),
            "alteracao_label": "Responsável",
            "alteracao_de": NAO_ATRIBUIDO,
            "alteracao_para": nome_destinatario,
            "texto_label": None,
            "texto_corpo": None,
        }

    return {
        "evento_tipo": "Mudança de responsável",
        "evento_titulo": "Você foi desvinculado de um chamado",
        "evento_descricao": "Você não é mais responsável por este chamado.",
        "alteracao_label": "Responsável",
        "alteracao_de": nome_destinatario,
        "alteracao_para": NAO_ATRIBUIDO,
        "texto_label": None,
        "texto_corpo": None,
    }


def montar_variaveis_email(item: dict, destinatario: dict, metadados: dict, nome_destinatario: str) -> dict:
    tipo_evento = item["tipo_evento"]
    identificador = metadados["identificador"]

    if tipo_evento == "taskCreated":
        contexto_evento = _contexto_criacao(metadados)
    elif tipo_evento == "taskCommentPosted":
        contexto_evento = _contexto_comentario(identificador)
    elif tipo_evento == "taskStatusUpdated":
        contexto_evento = _contexto_status(identificador, item.get("before"), item.get("after"))
    else:
        contexto_evento = _contexto_atribuicao(destinatario.get("papel"), nome_destinatario)

    status_exibicao = metadados["status_atual"] or "-"

    return {
        "email_assunto": f"Clickup | [{identificador}] {contexto_evento['evento_tipo']}",
        "evento_resumo": contexto_evento["evento_titulo"],
        "cor_evento": _cor_por_status(status_exibicao),
        "empresa_sigla": EMPRESA_SIGLA,
        "empresa_nome": EMPRESA_NOME,
        "empresa_logo_url": EMPRESA_LOGO_URL,
        "destinatario_nome": nome_destinatario,
        "chamado_id": identificador,
        "chamado_titulo": metadados["titulo"] or "(sem título)",
        "status_atual": status_exibicao,
        "responsavel": metadados["responsavel_nome"],
        "solicitante": metadados["solicitante_nome"],
        "prioridade": metadados["prioridade"] or "-",
        "data_evento": _formatar_data(item.get("data_epoch_ms")),
        "chamado_url": f"https://app.clickup.com/t/{item['task_id']}",
        **contexto_evento,
    }


def renderizar_email(variaveis: dict) -> str:
    return _TEMPLATE.render(**variaveis)


def montar_email(item: dict, destinatario: dict, metadados: dict, nome_destinatario: str) -> tuple[str, str]:
    variaveis = montar_variaveis_email(item, destinatario, metadados, nome_destinatario)
    return variaveis["email_assunto"], renderizar_email(variaveis)

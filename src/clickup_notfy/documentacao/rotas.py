"""Descricao das rotas da API, mantida manualmente ao lado do codigo.

Nao gera nada automaticamente a partir das rotas do Flask - e uma lista
escrita a mao, que precisa ser atualizada quando uma rota muda. Trade-off
deliberado: evita a complexidade de um gerador de OpenAPI/Swagger para uma
API pequena como esta.
"""

DESCRICAO_ROTAS = [
    {
        "metodo": "POST",
        "caminho": "/webhooks/clickup",
        "descricao": "Recebe eventos do webhook do ClickUp (taskCreated, taskStatusUpdated, taskCommentPosted, taskAssigneeUpdated).",
        "autenticacao": "Assinatura HMAC-SHA256 no header X-Signature (nao usa Bearer token).",
        "corpo_requisicao": "Payload de webhook do ClickUp (ver ADR-0006 em docs/adr/).",
        "respostas": {
            "200": "Evento aceito e processado (ou ignorado, se fora do escopo suportado).",
            "401": "Assinatura ausente ou invalida.",
            "502": "Falha ao resolver destinatarios (ex: API do ClickUp indisponivel) - o ClickUp deve reentregar.",
        },
    },
    {
        "metodo": "POST",
        "caminho": "/mapeamentos-email",
        "descricao": "Cadastra um mapeamento de identidade ClickUp -> email oficial.",
        "autenticacao": "Bearer token (header Authorization: Bearer <API_BEARER_TOKEN>).",
        "corpo_requisicao": {
            "clickup_user_id": "int, obrigatorio",
            "clickup_email": "string, obrigatorio",
            "official_email": "string, obrigatorio",
            "nome": "string, obrigatorio",
        },
        "respostas": {
            "201": "Mapeamento criado - retorna o registro.",
            "400": "Campo obrigatorio faltando.",
            "401": "Token ausente ou invalido.",
            "409": "Ja existe mapeamento para esse clickup_user_id.",
        },
    },
    {
        "metodo": "GET",
        "caminho": "/mapeamentos-email",
        "descricao": "Lista os mapeamentos cadastrados.",
        "autenticacao": "Bearer token (header Authorization: Bearer <API_BEARER_TOKEN>).",
        "parametros_query": {"ativo": "opcional, 'true'/'false' - filtra por status"},
        "respostas": {"200": "Lista de mapeamentos.", "401": "Token ausente ou invalido."},
    },
    {
        "metodo": "GET",
        "caminho": "/mapeamentos-email/<clickup_user_id>",
        "descricao": "Detalha um mapeamento especifico.",
        "autenticacao": "Bearer token (header Authorization: Bearer <API_BEARER_TOKEN>).",
        "respostas": {
            "200": "Mapeamento encontrado.",
            "401": "Token ausente ou invalido.",
            "404": "Nao encontrado.",
        },
    },
    {
        "metodo": "PATCH",
        "caminho": "/mapeamentos-email/<clickup_user_id>",
        "descricao": "Atualiza campos de um mapeamento (ex: corrigir official_email, ou desativar com ativo: false).",
        "autenticacao": "Bearer token (header Authorization: Bearer <API_BEARER_TOKEN>).",
        "corpo_requisicao": {
            "clickup_email": "string, opcional",
            "official_email": "string, opcional",
            "nome": "string, opcional",
            "ativo": "bool, opcional",
        },
        "respostas": {
            "200": "Mapeamento atualizado - retorna o registro.",
            "401": "Token ausente ou invalido.",
            "404": "Nao encontrado.",
        },
    },
]

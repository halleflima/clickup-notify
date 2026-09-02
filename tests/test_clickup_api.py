import json

import pytest
import requests
import responses

from clickup_notfy.clickup_api import (
    buscar_saude_webhook,
    buscar_tarefa,
    extrair_descricao,
    extrair_nome_tarefa,
    extrair_prioridade,
    extrair_responsaveis,
    extrair_responsaveis_ids,
    extrair_solicitantes,
    extrair_solicitantes_ids,
    extrair_status_atual,
    reativar_webhook,
)


@responses.activate
def test_buscar_tarefa_envia_token_no_header():
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"id": "abc123", "assignees": []},
        status=200,
    )

    tarefa = buscar_tarefa("abc123", token="pk_teste")

    assert tarefa["id"] == "abc123"
    assert responses.calls[0].request.headers["Authorization"] == "pk_teste"


def test_extrair_responsaveis_ids():
    tarefa = {"assignees": [{"id": 111, "username": "fulano"}, {"id": 222, "username": "ciclana"}]}

    assert extrair_responsaveis_ids(tarefa) == [111, 222]


def test_extrair_responsaveis_ids_sem_assignees():
    assert extrair_responsaveis_ids({}) == []


def test_extrair_solicitantes_ids_campo_com_lista_de_uma_pessoa():
    tarefa = {
        "custom_fields": [
            {"name": "Solicitante", "value": [{"id": 333, "username": "solicitante"}]}
        ]
    }

    assert extrair_solicitantes_ids(tarefa) == [333]


def test_extrair_solicitantes_ids_campo_com_lista_de_varias_pessoas():
    """ADR-0012: o campo de pessoa do ClickUp pode ter mais de uma pessoa
    selecionada - todas devem ser extraidas, nao so a primeira."""
    tarefa = {
        "custom_fields": [
            {
                "name": "Solicitante",
                "value": [
                    {"id": 333, "username": "primeiro"},
                    {"id": 444, "username": "segundo"},
                ],
            }
        ]
    }

    assert extrair_solicitantes_ids(tarefa) == [333, 444]


def test_extrair_solicitantes_ids_campo_com_objeto_unico():
    tarefa = {"custom_fields": [{"name": "Solicitante", "value": {"id": 333}}]}

    assert extrair_solicitantes_ids(tarefa) == [333]


def test_extrair_solicitantes_ids_campo_vazio_retorna_lista_vazia():
    tarefa = {"custom_fields": [{"name": "Solicitante", "value": []}]}

    assert extrair_solicitantes_ids(tarefa) == []


def test_extrair_solicitantes_ids_campo_ausente_retorna_lista_vazia():
    tarefa = {"custom_fields": [{"name": "Outro Campo", "value": "x"}]}

    assert extrair_solicitantes_ids(tarefa) == []


def test_extrair_solicitantes_ids_sem_custom_fields_retorna_lista_vazia():
    assert extrair_solicitantes_ids({}) == []


def test_extrair_responsaveis_traz_email_e_nome():
    tarefa = {"assignees": [{"id": 111, "username": "fulano", "email": "fulano@gmail.com"}]}

    assert extrair_responsaveis(tarefa) == [
        {"id": 111, "email": "fulano@gmail.com", "nome": "fulano"}
    ]


def test_extrair_solicitantes_traz_email_e_nome():
    tarefa = {
        "custom_fields": [
            {
                "name": "Solicitante",
                "value": [{"id": 333, "username": "ciclano", "email": "ciclano@gmail.com"}],
            }
        ]
    }

    assert extrair_solicitantes(tarefa) == [{"id": 333, "email": "ciclano@gmail.com", "nome": "ciclano"}]


def test_extrair_solicitantes_com_mais_de_uma_pessoa():
    tarefa = {
        "custom_fields": [
            {
                "name": "Solicitante",
                "value": [
                    {"id": 333, "username": "ciclano", "email": "ciclano@gmail.com"},
                    {"id": 444, "username": "beltrano", "email": "beltrano@gmail.com"},
                ],
            }
        ]
    }

    assert extrair_solicitantes(tarefa) == [
        {"id": 333, "email": "ciclano@gmail.com", "nome": "ciclano"},
        {"id": 444, "email": "beltrano@gmail.com", "nome": "beltrano"},
    ]


def test_extrair_solicitantes_sem_email_retorna_none_no_campo():
    tarefa = {"custom_fields": [{"name": "Solicitante", "value": {"id": 333}}]}

    assert extrair_solicitantes(tarefa) == [{"id": 333, "email": None, "nome": None}]


def test_extrair_solicitantes_com_emoji_no_nome_do_campo():
    """Formato real confirmado em producao: o campo customizado no ClickUp
    tem um emoji/prefixo no nome (ex: "\U0001f468\u200d\u2696\ufe0f Solicitante"),
    entao uma comparacao exata de nome nunca bateria."""
    tarefa = {
        "custom_fields": [
            {
                "name": "\U0001f468\u200d\u2696\ufe0f Solicitante",
                "value": [{"id": 82174980, "username": "Hallef Lima", "email": "hallef@gmail.com"}],
            }
        ]
    }

    assert extrair_solicitantes(tarefa) == [
        {"id": 82174980, "email": "hallef@gmail.com", "nome": "Hallef Lima"}
    ]


def test_extrair_solicitantes_e_case_insensitive():
    tarefa = {
        "custom_fields": [
            {"name": "SOLICITANTE", "value": {"id": 111, "username": "x", "email": "x@gmail.com"}}
        ]
    }

    assert extrair_solicitantes(tarefa)[0]["id"] == 111


def test_extrair_prioridade_traduzida():
    assert extrair_prioridade({"priority": {"priority": "urgent"}}) == "Urgente"
    assert extrair_prioridade({"priority": {"priority": "high"}}) == "Alta"
    assert extrair_prioridade({"priority": {"priority": "normal"}}) == "Normal"
    assert extrair_prioridade({"priority": {"priority": "low"}}) == "Baixa"


def test_extrair_prioridade_ausente_retorna_none():
    assert extrair_prioridade({"priority": None}) is None
    assert extrair_prioridade({}) is None


def test_extrair_status_atual():
    assert extrair_status_atual({"status": {"status": "em desenvolvimento"}}) == "em desenvolvimento"


def test_extrair_status_atual_ausente_retorna_none():
    assert extrair_status_atual({}) is None


def test_extrair_descricao_prefere_text_content():
    tarefa = {"text_content": "texto puro", "description": "texto com **markdown**"}
    assert extrair_descricao(tarefa) == "texto puro"


def test_extrair_descricao_ausente_retorna_none():
    assert extrair_descricao({}) is None


def test_extrair_nome_tarefa():
    assert extrair_nome_tarefa({"name": "Erro ao gerar boleto"}) == "Erro ao gerar boleto"


@responses.activate
def test_buscar_saude_webhook_encontra_pelo_id():
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/team/9007177246/webhook",
        json={
            "webhooks": [
                {"id": "outro-webhook", "health": {"status": "active", "fail_count": 0}},
                {"id": "cc6e40b3", "health": {"status": "suspended", "fail_count": 101}},
            ]
        },
        status=200,
    )

    saude = buscar_saude_webhook("9007177246", "cc6e40b3", token="pk_teste")

    assert saude == {"status": "suspended", "fail_count": 101}


@responses.activate
def test_buscar_saude_webhook_retorna_none_se_id_nao_encontrado():
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/team/9007177246/webhook",
        json={"webhooks": [{"id": "outro-webhook", "health": {"status": "active", "fail_count": 0}}]},
        status=200,
    )

    saude = buscar_saude_webhook("9007177246", "webhook-inexistente", token="pk_teste")

    assert saude is None


@responses.activate
def test_reativar_webhook_envia_status_active():
    responses.add(
        responses.PUT,
        "https://api.clickup.com/api/v2/webhook/cc6e40b3-a76e-4d13-ab79-647106ddad99",
        json={"id": "cc6e40b3-a76e-4d13-ab79-647106ddad99", "webhook": {"health": {"status": "active"}}},
        status=200,
    )

    reativar_webhook("cc6e40b3-a76e-4d13-ab79-647106ddad99", token="pk_teste")

    assert responses.calls[0].request.headers["Authorization"] == "pk_teste"
    assert json.loads(responses.calls[0].request.body) == {"status": "active"}


@responses.activate
def test_reativar_webhook_propaga_erro_http():
    responses.add(
        responses.PUT,
        "https://api.clickup.com/api/v2/webhook/webhook-invalido",
        json={"err": "Webhook not found"},
        status=404,
    )

    with pytest.raises(requests.HTTPError):
        reativar_webhook("webhook-invalido", token="pk_teste")

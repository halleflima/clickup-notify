import responses

from clickup_notfy.clickup_api import (
    buscar_tarefa,
    extrair_descricao,
    extrair_nome_tarefa,
    extrair_prioridade,
    extrair_responsaveis,
    extrair_responsaveis_ids,
    extrair_solicitante,
    extrair_solicitante_id,
    extrair_status_atual,
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


def test_extrair_solicitante_id_campo_com_lista_de_pessoa():
    tarefa = {
        "custom_fields": [
            {"name": "Solicitante", "value": [{"id": 333, "username": "solicitante"}]}
        ]
    }

    assert extrair_solicitante_id(tarefa) == 333


def test_extrair_solicitante_id_campo_com_objeto_unico():
    tarefa = {"custom_fields": [{"name": "Solicitante", "value": {"id": 333}}]}

    assert extrair_solicitante_id(tarefa) == 333


def test_extrair_solicitante_id_campo_vazio_retorna_none():
    tarefa = {"custom_fields": [{"name": "Solicitante", "value": []}]}

    assert extrair_solicitante_id(tarefa) is None


def test_extrair_solicitante_id_campo_ausente_retorna_none():
    tarefa = {"custom_fields": [{"name": "Outro Campo", "value": "x"}]}

    assert extrair_solicitante_id(tarefa) is None


def test_extrair_solicitante_id_sem_custom_fields_retorna_none():
    assert extrair_solicitante_id({}) is None


def test_extrair_responsaveis_traz_email_e_nome():
    tarefa = {"assignees": [{"id": 111, "username": "fulano", "email": "fulano@gmail.com"}]}

    assert extrair_responsaveis(tarefa) == [
        {"id": 111, "email": "fulano@gmail.com", "nome": "fulano"}
    ]


def test_extrair_solicitante_traz_email_e_nome():
    tarefa = {
        "custom_fields": [
            {
                "name": "Solicitante",
                "value": [{"id": 333, "username": "ciclano", "email": "ciclano@gmail.com"}],
            }
        ]
    }

    assert extrair_solicitante(tarefa) == {"id": 333, "email": "ciclano@gmail.com", "nome": "ciclano"}


def test_extrair_solicitante_sem_email_retorna_none_no_campo():
    tarefa = {"custom_fields": [{"name": "Solicitante", "value": {"id": 333}}]}

    assert extrair_solicitante(tarefa) == {"id": 333, "email": None, "nome": None}


def test_extrair_solicitante_com_emoji_no_nome_do_campo():
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

    assert extrair_solicitante(tarefa) == {
        "id": 82174980,
        "email": "hallef@gmail.com",
        "nome": "Hallef Lima",
    }


def test_extrair_solicitante_e_case_insensitive():
    tarefa = {
        "custom_fields": [
            {"name": "SOLICITANTE", "value": {"id": 111, "username": "x", "email": "x@gmail.com"}}
        ]
    }

    assert extrair_solicitante(tarefa)["id"] == 111


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

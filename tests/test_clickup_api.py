import responses

from clickup_notfy.clickup_api import (
    buscar_tarefa,
    extrair_responsaveis,
    extrair_responsaveis_ids,
    extrair_solicitante,
    extrair_solicitante_id,
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

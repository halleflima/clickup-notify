import pytest
import responses

from clickup_notfy import db
from clickup_notfy.mapeamentos import repository as mapeamentos_repository
from clickup_notfy.notificacoes.processador import processar_evento

CONFIG = {
    "CLICKUP_API_TOKEN": "pk_teste",
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "usuario",
    "SMTP_PASSWORD": "senha",
    "EMAIL_REMETENTE": "notificacao@empresa.com",
    "FALLBACK_EMAIL": "fallback@empresa.com",
}


@pytest.fixture
def conexao():
    conexao = db.conectar(":memory:")
    db.inicializar_schema(conexao)
    yield conexao
    conexao.close()


@pytest.fixture(autouse=True)
def sem_envio_real(monkeypatch):
    monkeypatch.setattr(
        "clickup_notfy.notificacoes.processador.email_sender.tentar_enviar", lambda *a, **k: True
    )


def item_criacao(evento_id="hist-1"):
    return {
        "id": evento_id,
        "tipo_evento": "taskCreated",
        "task_id": "abc123",
        "autor_id": 999,
        "before": None,
        "after": None,
    }


@responses.activate
def test_processa_criacao_usa_email_do_mapeamento(conexao):
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}]},
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert len(notificacoes) == 1
    assert notificacoes[0]["destinatario_email"] == "fulano@empresa.com"
    assert notificacoes[0]["status"] == "enviado"


@responses.activate
def test_processa_criacao_sem_mapeamento_e_sem_email_usa_fallback(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 999}}]},
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "fallback@empresa.com"


@responses.activate
def test_processa_criacao_sem_mapeamento_mas_com_email_auto_cadastra(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "assignees": [],
            "custom_fields": [
                {
                    "name": "Solicitante",
                    "value": {"id": 555, "username": "novato", "email": "novato@gmail.com"},
                }
            ],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "novato@gmail.com"

    mapeamento = mapeamentos_repository.buscar_por_id(conexao, 555)
    assert mapeamento["clickup_email"] == "novato@gmail.com"
    assert mapeamento["official_email"] == "novato@gmail.com"
    assert mapeamento["nome"] == "novato"
    assert mapeamento["ativo"] is True


@responses.activate
def test_processa_criacao_reusa_mapeamento_auto_cadastrado_na_segunda_vez(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "assignees": [],
            "custom_fields": [
                {
                    "name": "Solicitante",
                    "value": {"id": 555, "username": "novato", "email": "novato@gmail.com"},
                }
            ],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(evento_id="hist-1"), CONFIG)
    processar_evento(conexao, item_criacao(evento_id="hist-2"), CONFIG)

    mapeamentos = mapeamentos_repository.listar(conexao)
    assert len(mapeamentos) == 1


@responses.activate
def test_processa_criacao_mapeamento_inativo_usa_fallback(conexao):
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")
    mapeamentos_repository.atualizar(conexao, 111, {"ativo": False})
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}]},
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "fallback@empresa.com"


def test_processa_atribuicao_nao_chama_api_do_clickup(conexao):
    mapeamentos_repository.criar(conexao, 222, "ciclano@gmail.com", "ciclano@empresa.com", "Ciclano")
    item = {
        "id": "hist-2",
        "tipo_evento": "taskAssigneeUpdated",
        "task_id": "abc123",
        "autor_id": 999,
        "before": [],
        "after": [222],
    }

    with responses.RequestsMock():
        processar_evento(conexao, item, CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "ciclano@empresa.com"

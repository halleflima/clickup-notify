import pytest

from clickup_notfy.app import create_app
from clickup_notfy.config import Config

TOKEN = "token-secreto"


class ConfigDeTeste(Config):
    API_BEARER_TOKEN = TOKEN


@pytest.fixture
def client(tmp_path):
    ConfigDeTeste.DATABASE_PATH = str(tmp_path / "teste.db")
    app = create_app(ConfigDeTeste)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def autorizacao():
    return {"Authorization": f"Bearer {TOKEN}"}


def payload_mapeamento(clickup_user_id=111):
    return {
        "clickup_user_id": clickup_user_id,
        "clickup_email": "fulano@gmail.com",
        "official_email": "fulano@empresa.com",
        "nome": "Fulano",
    }


def test_rotas_exigem_autenticacao(client):
    assert client.get("/mapeamentos-email").status_code == 401
    assert client.post("/mapeamentos-email", json=payload_mapeamento()).status_code == 401


def test_criar_e_listar_mapeamento(client):
    resposta_criacao = client.post(
        "/mapeamentos-email", json=payload_mapeamento(), headers=autorizacao()
    )
    assert resposta_criacao.status_code == 201

    resposta_listagem = client.get("/mapeamentos-email", headers=autorizacao())
    assert resposta_listagem.status_code == 200
    assert len(resposta_listagem.get_json()) == 1


def test_criar_mapeamento_duplicado_retorna_conflito(client):
    client.post("/mapeamentos-email", json=payload_mapeamento(), headers=autorizacao())
    resposta = client.post("/mapeamentos-email", json=payload_mapeamento(), headers=autorizacao())

    assert resposta.status_code == 409


def test_criar_mapeamento_sem_campo_obrigatorio_retorna_400(client):
    dados = payload_mapeamento()
    del dados["nome"]

    resposta = client.post("/mapeamentos-email", json=dados, headers=autorizacao())

    assert resposta.status_code == 400


def test_obter_mapeamento_inexistente_retorna_404(client):
    resposta = client.get("/mapeamentos-email/999", headers=autorizacao())
    assert resposta.status_code == 404


def test_atualizar_mapeamento_para_desativar(client):
    client.post("/mapeamentos-email", json=payload_mapeamento(), headers=autorizacao())

    resposta = client.patch(
        "/mapeamentos-email/111", json={"ativo": False}, headers=autorizacao()
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["ativo"] is False

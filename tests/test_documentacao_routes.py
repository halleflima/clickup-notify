import pytest

from clickup_notfy.app import create_app
from clickup_notfy.config import Config


class ConfigDeTeste(Config):
    pass


@pytest.fixture
def client(tmp_path):
    ConfigDeTeste.DATABASE_PATH = str(tmp_path / "teste.db")
    app = create_app(ConfigDeTeste)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_rota_raiz_nao_exige_autenticacao(client):
    resposta = client.get("/")

    assert resposta.status_code == 200


def test_rota_raiz_lista_as_rotas_conhecidas(client):
    dados = client.get("/").get_json()

    caminhos = {rota["caminho"] for rota in dados["rotas"]}
    assert "/webhooks/clickup" in caminhos
    assert "/mapeamentos-email" in caminhos
    assert "/mapeamentos-email/<clickup_user_id>" in caminhos

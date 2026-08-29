import pytest
from flask import Flask

from clickup_notfy.auth import exigir_bearer_token

TOKEN = "token-secreto"


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["API_BEARER_TOKEN"] = TOKEN

    @app.route("/protegida")
    @exigir_bearer_token
    def protegida():
        return {"ok": True}

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_sem_header_de_autorizacao_e_rejeitado(client):
    assert client.get("/protegida").status_code == 401


def test_token_incorreto_e_rejeitado(client):
    resposta = client.get("/protegida", headers={"Authorization": "Bearer errado"})
    assert resposta.status_code == 401


def test_token_correto_e_aceito(client):
    resposta = client.get("/protegida", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resposta.status_code == 200

import hashlib
import hmac
import json

import pytest

from clickup_notfy import db
from clickup_notfy.app import create_app
from clickup_notfy.config import Config

SECRET = "segredo-do-webhook"


class ConfigDeTeste(Config):
    CLICKUP_WEBHOOK_SECRET = SECRET


def assinar(corpo: bytes) -> str:
    return hmac.new(SECRET.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


@pytest.fixture
def client(tmp_path):
    ConfigDeTeste.DATABASE_PATH = str(tmp_path / "teste.db")
    app = create_app(ConfigDeTeste)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def payload_bruto(evento_id="hist-1"):
    payload = {
        "event": "taskCreated",
        "task_id": "abc123",
        "history_items": [{"id": evento_id, "user": {"id": 111}, "before": None, "after": None}],
    }
    return json.dumps(payload).encode("utf-8")


def test_requisicao_sem_assinatura_e_rejeitada(client):
    resposta = client.post("/webhooks/clickup", data=payload_bruto(), content_type="application/json")

    assert resposta.status_code == 401


def test_requisicao_com_assinatura_valida_e_aceita(client):
    corpo = payload_bruto()

    resposta = client.post(
        "/webhooks/clickup",
        data=corpo,
        content_type="application/json",
        headers={"X-Signature": assinar(corpo)},
    )

    assert resposta.status_code == 200


def test_evento_duplicado_nao_e_registrado_duas_vezes(client):
    corpo = payload_bruto(evento_id="hist-dup")
    headers = {"X-Signature": assinar(corpo)}

    client.post("/webhooks/clickup", data=corpo, content_type="application/json", headers=headers)
    resposta = client.post("/webhooks/clickup", data=corpo, content_type="application/json", headers=headers)

    assert resposta.status_code == 200

    conexao = db.conectar(ConfigDeTeste.DATABASE_PATH)
    total = conexao.execute(
        "SELECT COUNT(*) AS total FROM eventos_processados WHERE id = ?", ("hist-dup",)
    ).fetchone()["total"]
    conexao.close()

    assert total == 1

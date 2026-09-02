import hashlib
import hmac
import json

import pytest
import responses

from clickup_notfy import db
from clickup_notfy.app import create_app
from clickup_notfy.config import Config

SECRET = "segredo-do-webhook"


class ConfigDeTeste(Config):
    CLICKUP_WEBHOOK_SECRET = SECRET
    CLICKUP_API_TOKEN = "pk_teste"
    FALLBACK_EMAIL = "fallback@empresa.com"
    EMAILS_ALERTA_OPERACIONAL = "admin@empresa.com"


def assinar(corpo: bytes) -> str:
    return hmac.new(SECRET.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


@pytest.fixture
def client(tmp_path, monkeypatch):
    ConfigDeTeste.DATABASE_PATH = str(tmp_path / "teste.db")
    monkeypatch.setattr(
        "clickup_notfy.notificacoes.processador.email_sender.tentar_enviar", lambda *a, **k: True
    )
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


def mockar_tarefa_no_clickup():
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": []},
        status=200,
    )


def test_requisicao_sem_assinatura_e_rejeitada(client):
    resposta = client.post("/webhooks/clickup", data=payload_bruto(), content_type="application/json")

    assert resposta.status_code == 401


@responses.activate
def test_requisicao_com_assinatura_valida_e_aceita(client):
    mockar_tarefa_no_clickup()
    corpo = payload_bruto()

    resposta = client.post(
        "/webhooks/clickup",
        data=corpo,
        content_type="application/json",
        headers={"X-Signature": assinar(corpo)},
    )

    assert resposta.status_code == 200


@responses.activate
def test_evento_duplicado_nao_e_registrado_duas_vezes(client):
    mockar_tarefa_no_clickup()
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


@responses.activate
def test_falha_ao_processar_evento_nao_registra_dedup(client):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        status=500,
    )
    corpo = payload_bruto(evento_id="hist-falha")
    headers = {"X-Signature": assinar(corpo)}

    resposta = client.post("/webhooks/clickup", data=corpo, content_type="application/json", headers=headers)

    assert resposta.status_code == 502

    conexao = db.conectar(ConfigDeTeste.DATABASE_PATH)
    total = conexao.execute(
        "SELECT COUNT(*) AS total FROM eventos_processados WHERE id = ?", ("hist-falha",)
    ).fetchone()["total"]
    conexao.close()

    assert total == 0


def test_evento_de_tipo_nao_suportado_e_aceito_e_ignorado(client):
    payload = {
        "event": "folderCreated",
        "task_id": None,
        "history_items": [{"id": "hist-irrelevante", "user": {"id": 111}, "before": None, "after": None}],
    }
    corpo = json.dumps(payload).encode("utf-8")

    with responses.RequestsMock():
        resposta = client.post(
            "/webhooks/clickup",
            data=corpo,
            content_type="application/json",
            headers={"X-Signature": assinar(corpo)},
        )

    assert resposta.status_code == 200


@responses.activate
def test_falha_ao_processar_evento_dispara_alerta_operacional(client, monkeypatch):
    alertas_enviados = []
    monkeypatch.setattr(
        'clickup_notfy.webhook.routes.alerta_operacional.email_sender.tentar_enviar',
        lambda config, destinatario, assunto, corpo: alertas_enviados.append(
            (destinatario, assunto, corpo)
        )
        or True,
    )
    responses.add(
        responses.GET,
        'https://api.clickup.com/api/v2/task/abc123',
        status=500,
    )
    corpo_webhook = payload_bruto(evento_id='hist-falha-alerta')
    headers = {'X-Signature': assinar(corpo_webhook)}

    resposta = client.post(
        '/webhooks/clickup', data=corpo_webhook, content_type='application/json', headers=headers
    )

    assert resposta.status_code == 502
    assert len(alertas_enviados) == 1
    destinatario, assunto, corpo_alerta = alertas_enviados[0]
    assert destinatario == 'admin@empresa.com'
    assert 'ClickUp Notify' in assunto
    assert 'hist-falha-alerta' in corpo_alerta

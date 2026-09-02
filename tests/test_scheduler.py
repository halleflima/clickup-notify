import json

import pytest
import responses

from clickup_notfy import db
from clickup_notfy.notificacoes import outbox_repository
from clickup_notfy.scheduler import (
    iniciar_scheduler,
    purgar_notificacoes_antigas,
    retentar_pendentes,
    verificar_saude_webhook,
)

CONFIG = {
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "usuario",
    "SMTP_PASSWORD": "senha",
    "EMAIL_REMETENTE": "notificacao@empresa.com",
}


@pytest.fixture
def conexao(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conexao = db.conectar(caminho)
    db.inicializar_schema(conexao)
    conexao.close()
    return caminho


def test_retentar_pendentes_marca_como_enviado_quando_smtp_funciona(conexao, monkeypatch):
    monkeypatch.setattr(
        "clickup_notfy.scheduler.email_sender.tentar_enviar", lambda *a, **k: True
    )
    conexao_db = db.conectar(conexao)
    notificacao_id = outbox_repository.criar_pendente(
        conexao_db, "hist-1", "abc123", "a@empresa.com", "taskCreated", "Assunto", "Corpo"
    )
    conexao_db.close()

    config = dict(CONFIG, DATABASE_PATH=conexao)
    retentar_pendentes(config)

    conexao_db = db.conectar(conexao)
    linha = conexao_db.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    conexao_db.close()
    assert linha["status"] == "enviado"


def test_retentar_pendentes_mantem_pendente_quando_smtp_falha(conexao, monkeypatch):
    monkeypatch.setattr(
        "clickup_notfy.scheduler.email_sender.tentar_enviar", lambda *a, **k: False
    )
    conexao_db = db.conectar(conexao)
    notificacao_id = outbox_repository.criar_pendente(
        conexao_db, "hist-1", "abc123", "a@empresa.com", "taskCreated", "Assunto", "Corpo"
    )
    conexao_db.close()

    config = dict(CONFIG, DATABASE_PATH=conexao)
    retentar_pendentes(config)

    conexao_db = db.conectar(conexao)
    linha = conexao_db.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    conexao_db.close()
    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 1


def test_purgar_remove_notificacoes_com_mais_de_dois_anos(conexao):
    conexao_db = db.conectar(conexao)
    conexao_db.execute(
        """
        INSERT INTO notificacoes_enviadas
            (evento_id, destinatario_email, tipo_evento, assunto, corpo, created_at)
        VALUES ('hist-antigo', 'a@empresa.com', 'taskCreated', 'A', 'B', datetime('now', '-3 years'))
        """
    )
    conexao_db.execute(
        """
        INSERT INTO notificacoes_enviadas
            (evento_id, destinatario_email, tipo_evento, assunto, corpo, created_at)
        VALUES ('hist-recente', 'a@empresa.com', 'taskCreated', 'A', 'B', datetime('now'))
        """
    )
    conexao_db.commit()
    conexao_db.close()

    removidos = purgar_notificacoes_antigas({"DATABASE_PATH": conexao})

    assert removidos == 1
    conexao_db = db.conectar(conexao)
    restantes = conexao_db.execute("SELECT evento_id FROM notificacoes_enviadas").fetchall()
    conexao_db.close()
    assert [r["evento_id"] for r in restantes] == ["hist-recente"]


def test_iniciar_scheduler_registra_os_quatro_jobs(conexao):
    scheduler = iniciar_scheduler(dict(CONFIG, DATABASE_PATH=conexao))
    try:
        ids = {job.id for job in scheduler.get_jobs()}
        assert ids == {
            "retry_pendentes",
            "purge_diario",
            "vacuum_mensal",
            "verificar_saude_webhook",
        }
    finally:
        scheduler.shutdown(wait=False)


CONFIG_SAUDE = dict(
    CONFIG,
    CLICKUP_API_TOKEN='pk_teste',
    CLICKUP_TEAM_ID='9007177246',
    CLICKUP_WEBHOOK_ID='cc6e40b3',
    EMAILS_ALERTA_OPERACIONAL='admin@empresa.com',
)


def _mockar_saude_webhook(status: str, fail_count: int):
    responses.add(
        responses.GET,
        'https://api.clickup.com/api/v2/team/9007177246/webhook',
        json={'webhooks': [{'id': 'cc6e40b3', 'health': {'status': status, 'fail_count': fail_count}}]},
        status=200,
    )


@responses.activate
def test_verificar_saude_webhook_sem_team_ou_webhook_id_nao_faz_nada(conexao):
    config = dict(CONFIG, DATABASE_PATH=conexao)

    verificar_saude_webhook(config)

    assert len(responses.calls) == 0


@responses.activate
def test_verificar_saude_webhook_abaixo_do_limite_nao_alerta(conexao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        'clickup_notfy.scheduler.alerta_operacional.email_sender.tentar_enviar',
        lambda *a, **k: chamadas.append(1) or True,
    )
    _mockar_saude_webhook(status='active', fail_count=3)

    verificar_saude_webhook(dict(CONFIG_SAUDE, DATABASE_PATH=conexao, LIMITE_FAIL_COUNT_ALERTA=20))

    assert chamadas == []


@responses.activate
def test_verificar_saude_webhook_no_limite_mas_nao_suspenso_nao_reativa(conexao, monkeypatch):
    """status 'failing' (nao 'suspended') mesmo acima do limite so alerta,
    nao tenta reativar - nao tem nada suspenso pra reativar. Se o codigo
    tentasse chamar o PUT de reativacao aqui, o teste falharia por causa
    da chamada HTTP nao mockada (responses.activate bloqueia por padrao)."""
    chamadas = []
    monkeypatch.setattr(
        'clickup_notfy.scheduler.alerta_operacional.email_sender.tentar_enviar',
        lambda *a, **k: chamadas.append(1) or True,
    )
    _mockar_saude_webhook(status='failing', fail_count=25)

    verificar_saude_webhook(dict(CONFIG_SAUDE, DATABASE_PATH=conexao, LIMITE_FAIL_COUNT_ALERTA=20))

    assert len(chamadas) == 1


@responses.activate
def test_verificar_saude_webhook_suspenso_reativa_automaticamente(conexao, monkeypatch):
    corpos_enviados = []
    monkeypatch.setattr(
        'clickup_notfy.scheduler.alerta_operacional.email_sender.tentar_enviar',
        lambda config, destinatario, assunto, corpo: corpos_enviados.append(corpo) or True,
    )
    _mockar_saude_webhook(status='suspended', fail_count=5)
    responses.add(
        responses.PUT,
        'https://api.clickup.com/api/v2/webhook/cc6e40b3',
        json={'webhook': {'health': {'status': 'active'}}},
        status=200,
    )

    verificar_saude_webhook(dict(CONFIG_SAUDE, DATABASE_PATH=conexao, LIMITE_FAIL_COUNT_ALERTA=20))

    assert len(corpos_enviados) == 1
    assert 'REATIVADO AUTOMATICAMENTE' in corpos_enviados[0]
    put_calls = [c for c in responses.calls if c.request.method == 'PUT']
    assert len(put_calls) == 1
    assert json.loads(put_calls[0].request.body) == {'status': 'active'}


@responses.activate
def test_verificar_saude_webhook_suspenso_reativacao_falha_ainda_alerta(conexao, monkeypatch):
    """Se a tentativa de reativar der erro (ex: ClickUp fora do ar), o
    alerta ainda e enviado - so sem afirmar que foi reativado."""
    corpos_enviados = []
    monkeypatch.setattr(
        'clickup_notfy.scheduler.alerta_operacional.email_sender.tentar_enviar',
        lambda config, destinatario, assunto, corpo: corpos_enviados.append(corpo) or True,
    )
    _mockar_saude_webhook(status='suspended', fail_count=5)
    responses.add(
        responses.PUT,
        'https://api.clickup.com/api/v2/webhook/cc6e40b3',
        json={'err': 'internal error'},
        status=500,
    )

    verificar_saude_webhook(dict(CONFIG_SAUDE, DATABASE_PATH=conexao, LIMITE_FAIL_COUNT_ALERTA=20))

    assert len(corpos_enviados) == 1
    assert 'REATIVADO AUTOMATICAMENTE' not in corpos_enviados[0]


@responses.activate
def test_verificar_saude_webhook_id_nao_encontrado_nao_quebra(conexao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        'clickup_notfy.scheduler.alerta_operacional.email_sender.tentar_enviar',
        lambda *a, **k: chamadas.append(1) or True,
    )
    responses.add(
        responses.GET,
        'https://api.clickup.com/api/v2/team/9007177246/webhook',
        json={'webhooks': []},
        status=200,
    )

    verificar_saude_webhook(dict(CONFIG_SAUDE, DATABASE_PATH=conexao))

    assert chamadas == []


def test_verificar_saude_webhook_erro_de_rede_nao_propaga(conexao, monkeypatch):
    def _levanta_erro(*a, **k):
        raise RuntimeError('timeout')

    monkeypatch.setattr('clickup_notfy.scheduler.clickup_api.buscar_saude_webhook', _levanta_erro)

    verificar_saude_webhook(dict(CONFIG_SAUDE, DATABASE_PATH=conexao))

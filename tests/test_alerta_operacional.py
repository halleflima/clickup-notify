import pytest

from clickup_notfy import db
from clickup_notfy.notificacoes.alerta_operacional import enviar_alerta_operacional

CONFIG_BASE = {
    'SMTP_HOST': 'smtp.exemplo.com',
    'SMTP_PORT': 587,
    'SMTP_USERNAME': 'usuario',
    'SMTP_PASSWORD': 'senha',
    'EMAIL_REMETENTE': 'notificacao@empresa.com',
    'EMAILS_ALERTA_OPERACIONAL': 'admin1@empresa.com, admin2@empresa.com',
}


@pytest.fixture
def conexao(tmp_path):
    caminho = str(tmp_path / 'teste.db')
    conexao = db.conectar(caminho)
    db.inicializar_schema(conexao)
    return conexao


def test_envia_para_cada_email_configurado(conexao, monkeypatch):
    enviados = []
    monkeypatch.setattr(
        'clickup_notfy.notificacoes.alerta_operacional.email_sender.tentar_enviar',
        lambda config, destinatario, assunto, corpo: enviados.append(destinatario) or True,
    )

    resultado = enviar_alerta_operacional(conexao, CONFIG_BASE, 'teste', 'Assunto', 'Mensagem')

    assert resultado is True
    assert enviados == ['admin1@empresa.com', 'admin2@empresa.com']


def test_sem_emails_configurados_nao_envia_nada(conexao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        'clickup_notfy.notificacoes.alerta_operacional.email_sender.tentar_enviar',
        lambda *a, **k: chamadas.append(1) or True,
    )
    config = dict(CONFIG_BASE, EMAILS_ALERTA_OPERACIONAL='')

    resultado = enviar_alerta_operacional(conexao, config, 'teste', 'Assunto', 'Mensagem')

    assert resultado is False
    assert chamadas == []


def test_segundo_alerta_do_mesmo_tipo_e_suprimido_por_cooldown(conexao, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        'clickup_notfy.notificacoes.alerta_operacional.email_sender.tentar_enviar',
        lambda *a, **k: chamadas.append(1) or True,
    )

    primeiro = enviar_alerta_operacional(conexao, CONFIG_BASE, 'mesmo-tipo', 'Assunto', 'Mensagem')
    segundo = enviar_alerta_operacional(conexao, CONFIG_BASE, 'mesmo-tipo', 'Assunto', 'Mensagem de novo')

    assert primeiro is True
    assert segundo is False
    assert len(chamadas) == 2  # so o primeiro envio (2 destinatarios), nao o segundo


def test_tipos_diferentes_nao_compartilham_cooldown(conexao, monkeypatch):
    monkeypatch.setattr(
        'clickup_notfy.notificacoes.alerta_operacional.email_sender.tentar_enviar',
        lambda *a, **k: True,
    )

    primeiro = enviar_alerta_operacional(conexao, CONFIG_BASE, 'tipo-a', 'Assunto', 'Mensagem')
    segundo = enviar_alerta_operacional(conexao, CONFIG_BASE, 'tipo-b', 'Assunto', 'Mensagem')

    assert primeiro is True
    assert segundo is True


def test_falha_ao_enviar_para_um_destinatario_nao_impede_os_demais(conexao, monkeypatch):
    enviados = []

    def _tentar_enviar(config, destinatario, assunto, corpo):
        if destinatario == 'admin1@empresa.com':
            raise RuntimeError('SMTP explodiu')
        enviados.append(destinatario)
        return True

    monkeypatch.setattr(
        'clickup_notfy.notificacoes.alerta_operacional.email_sender.tentar_enviar', _tentar_enviar
    )

    resultado = enviar_alerta_operacional(conexao, CONFIG_BASE, 'teste', 'Assunto', 'Mensagem')

    assert resultado is True
    assert enviados == ['admin2@empresa.com']

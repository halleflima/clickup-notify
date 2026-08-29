import smtplib
from unittest.mock import MagicMock

from clickup_notfy.notificacoes.email_sender import tentar_enviar

CONFIG = {
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "usuario",
    "SMTP_PASSWORD": "senha",
    "EMAIL_REMETENTE": "notificacao@empresa.com",
}


def test_envio_bem_sucedido_retorna_true(monkeypatch):
    servidor_fake = MagicMock()
    servidor_fake.__enter__.return_value = servidor_fake
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: servidor_fake)

    sucesso = tentar_enviar(CONFIG, "fulano@empresa.com", "Assunto", "Corpo")

    assert sucesso is True
    servidor_fake.login.assert_called_once_with("usuario", "senha")
    servidor_fake.sendmail.assert_called_once()


def test_falha_de_conexao_retorna_false(monkeypatch):
    def levantar_erro(*args, **kwargs):
        raise OSError("conexao recusada")

    monkeypatch.setattr(smtplib, "SMTP", levantar_erro)

    sucesso = tentar_enviar(CONFIG, "fulano@empresa.com", "Assunto", "Corpo")

    assert sucesso is False


def test_falha_de_autenticacao_retorna_false(monkeypatch):
    servidor_fake = MagicMock()
    servidor_fake.__enter__.return_value = servidor_fake
    servidor_fake.login.side_effect = smtplib.SMTPAuthenticationError(535, b"credenciais invalidas")
    monkeypatch.setattr(smtplib, "SMTP", lambda *a, **k: servidor_fake)

    sucesso = tentar_enviar(CONFIG, "fulano@empresa.com", "Assunto", "Corpo")

    assert sucesso is False

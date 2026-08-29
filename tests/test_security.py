import hashlib
import hmac

from clickup_notfy.webhook.security import assinatura_valida

SECRET = "segredo-do-webhook"
CORPO = b'{"event":"taskCreated","task_id":"abc123"}'


def assinar(secret: str, corpo: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


def test_assinatura_correta_e_aceita():
    assinatura = assinar(SECRET, CORPO)
    assert assinatura_valida(SECRET, CORPO, assinatura) is True


def test_assinatura_incorreta_e_rejeitada():
    assinatura_errada = assinar("outro-segredo", CORPO)
    assert assinatura_valida(SECRET, CORPO, assinatura_errada) is False


def test_corpo_alterado_invalida_assinatura():
    assinatura = assinar(SECRET, CORPO)
    corpo_alterado = CORPO + b" "
    assert assinatura_valida(SECRET, corpo_alterado, assinatura) is False


def test_assinatura_vazia_e_rejeitada():
    assert assinatura_valida(SECRET, CORPO, "") is False


def test_secret_vazio_e_rejeitado():
    assinatura = assinar(SECRET, CORPO)
    assert assinatura_valida("", CORPO, assinatura) is False

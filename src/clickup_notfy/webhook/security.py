import hashlib
import hmac


def assinatura_valida(secret: str, corpo_bruto: bytes, assinatura_recebida: str) -> bool:
    if not secret or not assinatura_recebida:
        return False

    assinatura_esperada = hmac.new(secret.encode("utf-8"), corpo_bruto, hashlib.sha256).hexdigest()
    return hmac.compare_digest(assinatura_esperada, assinatura_recebida)

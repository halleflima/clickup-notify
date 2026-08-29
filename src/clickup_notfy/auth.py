import secrets
from functools import wraps

from flask import current_app, request


def exigir_bearer_token(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        token_esperado = current_app.config["API_BEARER_TOKEN"]
        cabecalho_recebido = request.headers.get("Authorization", "")

        if not token_esperado or not secrets.compare_digest(
            cabecalho_recebido, f"Bearer {token_esperado}"
        ):
            return {"erro": "nao autorizado"}, 401

        return funcao(*args, **kwargs)

    return wrapper

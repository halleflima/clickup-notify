import json

from flask import Blueprint, current_app, request

from clickup_notfy import db
from clickup_notfy.webhook.dedup import evento_ja_processado, registrar_evento
from clickup_notfy.webhook.parser import extrair_itens_historico
from clickup_notfy.webhook.security import assinatura_valida

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/webhooks/clickup", methods=["POST"])
def receber_evento_clickup():
    corpo_bruto = request.get_data()
    assinatura_recebida = request.headers.get("X-Signature", "")
    secret = current_app.config["CLICKUP_WEBHOOK_SECRET"]

    if not assinatura_valida(secret, corpo_bruto, assinatura_recebida):
        return {"erro": "assinatura invalida"}, 401

    payload = json.loads(corpo_bruto)
    itens = extrair_itens_historico(payload)

    conexao = db.conectar(current_app.config["DATABASE_PATH"])
    try:
        for item in itens:
            if evento_ja_processado(conexao, item["id"]):
                continue
            registrar_evento(
                conexao,
                evento_id=item["id"],
                tipo_evento=item["tipo_evento"],
                task_id=item["task_id"],
                payload_bruto=json.dumps(item),
            )
    finally:
        conexao.close()

    return {"status": "recebido"}, 200

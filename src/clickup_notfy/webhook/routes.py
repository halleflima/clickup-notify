import json
import logging

from flask import Blueprint, current_app, request

from clickup_notfy import db
from clickup_notfy.notificacoes import alerta_operacional
from clickup_notfy.notificacoes.processador import processar_evento
from clickup_notfy.webhook.dedup import evento_ja_processado, registrar_evento
from clickup_notfy.webhook.parser import extrair_itens_historico
from clickup_notfy.webhook.security import assinatura_valida

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)


@webhook_bp.route('/webhooks/clickup', methods=['POST'])
def receber_evento_clickup():
    corpo_bruto = request.get_data()
    assinatura_recebida = request.headers.get('X-Signature', '')
    secret = current_app.config['CLICKUP_WEBHOOK_SECRET']

    if not assinatura_valida(secret, corpo_bruto, assinatura_recebida):
        return {'erro': 'assinatura invalida'}, 401

    payload = json.loads(corpo_bruto)
    itens = extrair_itens_historico(payload)

    conexao = db.conectar(current_app.config['DATABASE_PATH'])
    try:
        for item in itens:
            if evento_ja_processado(conexao, item['id']):
                continue

            try:
                processar_evento(conexao, item, current_app.config)
            except Exception:
                logger.exception(
                    'Falha ao processar evento %s, sera reprocessado no proximo retry do ClickUp', item['id']
                )
                alerta_operacional.enviar_alerta_operacional(
                    conexao,
                    current_app.config,
                    tipo='falha_processamento_evento',
                    assunto='[ClickUp Notify] Falha ao processar evento do ClickUp',
                    mensagem=(
                        f'Falha ao processar o evento {item["id"]} '
                        f'(tipo {item.get("tipo_evento")}, task {item.get("task_id")}). '
                        f'O ClickUp deve reentregar esse evento automaticamente. '
                        f'Verifique os logs da aplicacao para o traceback completo.'
                    ),
                )
                return {'erro': 'falha ao processar evento'}, 502

            registrar_evento(
                conexao,
                evento_id=item['id'],
                tipo_evento=item['tipo_evento'],
                task_id=item['task_id'],
                payload_bruto=json.dumps(item),
            )
    finally:
        conexao.close()

    return {'status': 'recebido'}, 200

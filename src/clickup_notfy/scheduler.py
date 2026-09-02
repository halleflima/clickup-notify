import logging

from apscheduler.schedulers.background import BackgroundScheduler

from clickup_notfy import clickup_api, db
from clickup_notfy.notificacoes import alerta_operacional, email_sender, outbox_repository

logger = logging.getLogger(__name__)

RETENCAO_DIAS = 2 * 365
LIMITE_FAIL_COUNT_ALERTA_PADRAO = 20


def retentar_pendentes(config) -> None:
    conexao = db.conectar(config['DATABASE_PATH'])
    try:
        for pendente in outbox_repository.listar_pendentes(conexao):
            sucesso = email_sender.tentar_enviar(
                config, pendente['destinatario_email'], pendente['assunto'], pendente['corpo']
            )
            outbox_repository.registrar_resultado_envio(conexao, pendente['id'], sucesso)
    finally:
        conexao.close()


def purgar_notificacoes_antigas(config) -> int:
    conexao = db.conectar(config['DATABASE_PATH'])
    try:
        cursor = conexao.execute(
            f"DELETE FROM notificacoes_enviadas WHERE created_at < datetime('now', '-{RETENCAO_DIAS} days')"
        )
        conexao.commit()
        return cursor.rowcount
    finally:
        conexao.close()


def executar_vacuum(config) -> None:
    conexao = db.conectar(config['DATABASE_PATH'])
    try:
        conexao.execute('VACUUM')
    finally:
        conexao.close()


def verificar_saude_webhook(config) -> None:
    """Consulta periodicamente a saude do webhook no ClickUp (ADR-0011) e
    dispara um alerta operacional se o fail_count estiver perto do limite
    que leva o ClickUp a suspender o webhook automaticamente (confirmado em
    producao: suspensao ocorreu com fail_count=101 - o ClickUp nao publica
    o limite oficial, entao o padrao aqui e conservador).

    Sem CLICKUP_TEAM_ID/CLICKUP_WEBHOOK_ID configurados, o job nao faz nada
    (nao e obrigatorio configurar isso pra rodar o servico).
    """
    team_id = config.get('CLICKUP_TEAM_ID')
    webhook_id = config.get('CLICKUP_WEBHOOK_ID')
    if not team_id or not webhook_id:
        return

    try:
        saude = clickup_api.buscar_saude_webhook(team_id, webhook_id, config['CLICKUP_API_TOKEN'])
    except Exception:
        logger.exception('Falha ao consultar saude do webhook no ClickUp')
        return

    if saude is None:
        logger.warning('Webhook %s nao encontrado na listagem do ClickUp', webhook_id)
        return

    limite = int(config.get('LIMITE_FAIL_COUNT_ALERTA') or LIMITE_FAIL_COUNT_ALERTA_PADRAO)
    fail_count = saude.get('fail_count') or 0
    status = saude.get('status')

    if fail_count < limite and status != 'suspended':
        return

    conexao = db.conectar(config['DATABASE_PATH'])
    try:
        alerta_operacional.enviar_alerta_operacional(
            conexao,
            config,
            tipo='webhook_degradado',
            assunto='[ClickUp Notify] Webhook do ClickUp perto do limite de falhas',
            mensagem=(
                f'O webhook do ClickUp Notify esta com status "{status}" e {fail_count} '
                f'falhas de entrega registradas. Se atingir o limite, o ClickUp suspende o '
                f'webhook automaticamente e nenhum evento novo chega ate ser reativado '
                f'manualmente (PUT /v2/webhook/{{id}} com status=active).'
            ),
        )
    finally:
        conexao.close()


def iniciar_scheduler(config) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: retentar_pendentes(config), 'interval', minutes=5, id='retry_pendentes')
    scheduler.add_job(lambda: purgar_notificacoes_antigas(config), 'interval', days=1, id='purge_diario')
    scheduler.add_job(lambda: executar_vacuum(config), 'interval', days=30, id='vacuum_mensal')
    scheduler.add_job(
        lambda: verificar_saude_webhook(config), 'interval', minutes=15, id='verificar_saude_webhook'
    )
    scheduler.start()
    logger.info(
        'Scheduler iniciado: retry a cada 5min, purge diario, vacuum mensal, saude do webhook a cada 15min'
    )
    return scheduler

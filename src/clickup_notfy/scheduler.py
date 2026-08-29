import logging

from apscheduler.schedulers.background import BackgroundScheduler

from clickup_notfy import db
from clickup_notfy.notificacoes import email_sender, outbox_repository

logger = logging.getLogger(__name__)

RETENCAO_DIAS = 2 * 365


def retentar_pendentes(config) -> None:
    conexao = db.conectar(config["DATABASE_PATH"])
    try:
        for pendente in outbox_repository.listar_pendentes(conexao):
            sucesso = email_sender.tentar_enviar(
                config, pendente["destinatario_email"], pendente["assunto"], pendente["corpo"]
            )
            outbox_repository.registrar_resultado_envio(conexao, pendente["id"], sucesso)
    finally:
        conexao.close()


def purgar_notificacoes_antigas(config) -> int:
    conexao = db.conectar(config["DATABASE_PATH"])
    try:
        cursor = conexao.execute(
            f"DELETE FROM notificacoes_enviadas WHERE created_at < datetime('now', '-{RETENCAO_DIAS} days')"
        )
        conexao.commit()
        return cursor.rowcount
    finally:
        conexao.close()


def executar_vacuum(config) -> None:
    conexao = db.conectar(config["DATABASE_PATH"])
    try:
        conexao.execute("VACUUM")
    finally:
        conexao.close()


def iniciar_scheduler(config) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: retentar_pendentes(config), "interval", minutes=5, id="retry_pendentes")
    scheduler.add_job(lambda: purgar_notificacoes_antigas(config), "interval", days=1, id="purge_diario")
    scheduler.add_job(lambda: executar_vacuum(config), "interval", days=30, id="vacuum_mensal")
    scheduler.start()
    logger.info("Scheduler iniciado: retry a cada 5min, purge diario, vacuum mensal")
    return scheduler

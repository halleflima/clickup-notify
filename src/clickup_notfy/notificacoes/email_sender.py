import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def tentar_enviar(config, destinatario_email: str, assunto: str, corpo: str) -> bool:
    mensagem = MIMEText(corpo)
    mensagem["Subject"] = assunto
    mensagem["From"] = config["EMAIL_REMETENTE"]
    mensagem["To"] = destinatario_email

    try:
        with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10) as servidor:
            servidor.starttls()
            servidor.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            servidor.sendmail(config["EMAIL_REMETENTE"], [destinatario_email], mensagem.as_string())
        return True
    except (smtplib.SMTPException, OSError):
        logger.exception("Falha ao enviar email para %s", destinatario_email)
        return False

"""Alerta operacional para quem administra o servico (ADR-0011).

Distinto do FALLBACK_EMAIL (ADR-0004): FALLBACK_EMAIL e o destino de uma
notificacao NORMAL de chamado quando falta mapeamento de destinatario -
continua existindo e funcionando exatamente como antes, sem mudanca aqui.

Este modulo e sobre avisar que o PROPRIO SERVICO pode estar com problema
(falha nao tratada ao processar um evento, ou o webhook do ClickUp perto do
limite de falhas que leva a suspensao automatica) - para uma lista separada
e configuravel de destinatarios (EMAILS_ALERTA_OPERACIONAL).
"""

import html
import logging

from clickup_notfy.notificacoes import alerta_repository, email_sender

logger = logging.getLogger(__name__)

JANELA_COOLDOWN_MINUTOS = 6 * 60


def _lista_emails(config) -> list[str]:
    bruto = config.get('EMAILS_ALERTA_OPERACIONAL') or ''
    return [email.strip() for email in bruto.split(',') if email.strip()]


def enviar_alerta_operacional(conexao, config, tipo: str, assunto: str, mensagem: str) -> bool:
    """Envia o alerta pra cada email configurado em EMAILS_ALERTA_OPERACIONAL.

    Respeita um cooldown por 'tipo' (JANELA_COOLDOWN_MINUTOS) pra nao
    floodar a caixa de entrada se o mesmo problema persistir por muitas
    execucoes do scheduler ou muitos eventos seguidos - continua sendo
    reenviado periodicamente enquanto o problema nao for corrigido, so nao
    a cada ocorrencia individual.

    Melhor esforco na entrega em si: uma falha ao enviar pra um destinatario
    especifico (exception nao tratada por tentar_enviar) vira so um log e
    nao impede tentar os demais - avisar sobre um problema nao pode, por si
    so, causar outro (ex: derrubar a resposta do webhook por causa do envio
    do alerta).

    MAS o cooldown so e armado (`registrar_alerta`) se pelo menos um envio
    realmente teve sucesso (`tentar_enviar` retornou True) - confirmado em
    producao: sem essa checagem, uma falha de SMTP (ex: timeout de rede)
    fazia `tentar_enviar` devolver False silenciosamente, e o alerta era
    marcado como "enviado" mesmo sem ninguem ter recebido nada, travando
    6h de silencio real com o problema original ainda ativo. Se ninguem
    recebeu de fato, a proxima execucao do scheduler tenta de novo antes
    (sem esperar o cooldown), o que e o comportamento certo quando a
    entrega falhou de verdade.

    Retorna True se pelo menos um destinatario recebeu o alerta com
    sucesso; False se foi suprimido por cooldown, lista vazia, ou todas as
    tentativas de envio falharam.
    """
    destinatarios = _lista_emails(config)
    if not destinatarios:
        return False

    if alerta_repository.houve_alerta_recente(conexao, tipo, JANELA_COOLDOWN_MINUTOS):
        logger.info('Alerta operacional (%s) suprimido por cooldown', tipo)
        return False

    corpo_html = f'<pre style="font-family: monospace; white-space: pre-wrap;">{html.escape(mensagem)}</pre>'
    sucesso_algum = False
    for destinatario in destinatarios:
        try:
            if email_sender.tentar_enviar(config, destinatario, assunto, corpo_html):
                sucesso_algum = True
            else:
                logger.warning('Alerta operacional (%s) nao entregue para %s', tipo, destinatario)
        except Exception:
            logger.exception('Falha ao enviar alerta operacional (%s) para %s', tipo, destinatario)

    if not sucesso_algum:
        logger.warning(
            'Alerta operacional (%s) falhou para todos os destinatarios - cooldown NAO armado, '
            'proxima verificacao tenta de novo',
            tipo,
        )
        return False

    alerta_repository.registrar_alerta(conexao, tipo)
    return True

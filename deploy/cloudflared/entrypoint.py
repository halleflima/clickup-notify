#!/usr/bin/env python3
"""Entrypoint do container do cloudflared (ADR-0010, secao "Revisado:
reativacao automatica do tunel e do endpoint").

So usa a biblioteca padrao do Python (sem dependencias) de proposito -
mantem o container leve e evita puxar pip/apt so pra isso.

Sobe o cloudflared quick tunnel, observa o log em busca da URL publica
(nova a cada vez que o processo reinicia, ja que quick tunnel nao tem
identidade fixa) e, assim que encontra, atualiza o endpoint do webhook no
ClickUp via API - fechando o ciclo sem depender de ninguem perceber a
URL mudou e atualizar manualmente.

Nao faz parte do pacote clickup_notfy (src/) de proposito - e ferramenta
operacional do ambiente onde o tunel e usado, nao logica de negocio do
servico (mesma linha do ADR-0010, que ja trata o cloudflared como
workaround operacional, nao parte do codigo do servico).
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

PADRAO_URL_TUNEL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def atualizar_endpoint_webhook(webhook_id: str, endpoint_url: str, token: str) -> None:
    corpo = json.dumps({"endpoint": endpoint_url}).encode()
    req = urllib.request.Request(
        f"https://api.clickup.com/api/v2/webhook/{webhook_id}",
        data=corpo,
        method="PUT",
        headers={"Authorization": token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resposta:
        print(f"[watcher] ClickUp respondeu {resposta.status} ao atualizar endpoint", flush=True)


def main() -> int:
    origem = os.environ["TUNNEL_ORIGIN_URL"]
    webhook_id = os.environ["CLICKUP_WEBHOOK_ID"]
    token = os.environ["CLICKUP_API_TOKEN"]

    processo = subprocess.Popen(
        ["/usr/local/bin/cloudflared", "tunnel", "--url", origem, "--log=stdout"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url_ja_registrada = False

    for linha in processo.stdout:
        print(linha, end="", flush=True)  # repassa o log normal do cloudflared pro docker logs

        if url_ja_registrada:
            continue

        achou = PADRAO_URL_TUNEL.search(linha)
        if not achou:
            continue

        nova_url = achou.group(0)
        endpoint = f"{nova_url}/webhooks/clickup"
        print(f"[watcher] Nova URL de tunel detectada: {nova_url}", flush=True)

        try:
            atualizar_endpoint_webhook(webhook_id, endpoint, token)
            print(f"[watcher] Endpoint do webhook atualizado para {endpoint}", flush=True)
        except urllib.error.URLError:
            print("[watcher] Falha ao atualizar endpoint no ClickUp - log completo:", flush=True)
            import traceback

            traceback.print_exc()
        finally:
            # so tenta 1x por sessao do tunel - a URL nao muda de novo
            # enquanto esse mesmo processo do cloudflared continuar rodando
            url_ja_registrada = True

    return processo.wait()


if __name__ == "__main__":
    sys.exit(main())

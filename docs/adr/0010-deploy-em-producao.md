# ADR-0010: Deploy em produção

## Status
Aceito

## Contexto
O ambiente de desenvolvimento/teste local usa um Cloudflare Tunnel (`cloudflared tunnel --url`) pra expor o serviço publicamente, contornando o CGNAT da rede residencial usada pros testes. Esse mecanismo é só um workaround: a URL é efêmera (muda a cada reinício) e o túnel pode cair sozinho, exigindo atualizar o endpoint do webhook no ClickUp toda vez.

O servidor de produção é da própria empresa, com IP público fixo e já exposto à internet — não tem o problema de CGNAT que motivou o túnel. O ClickUp exige HTTPS para entregar webhooks, e o serviço (`gunicorn` na porta 5000) não faz TLS sozinho.

## Decisão
**Sem túnel em produção**: o Cloudflare Tunnel é exclusivo do ambiente de desenvolvimento local (documentado só operacionalmente, não faz parte do código do serviço). Em produção, o servidor recebe tráfego direto no IP fixo.

**Reverse proxy com TLS automático**: adicionado `docker-compose.prod.yml`, com um segundo serviço `caddy` (imagem oficial `caddy:2-alpine`) na frente do `clickup-notfy`. O Caddy:
- Expõe as portas 80/443 pro mundo externo.
- Emite e renova sozinho o certificado HTTPS via Let's Encrypt, a partir do domínio configurado em `DOMAIN` (variável de ambiente nova, só usada em produção).
- Encaminha as requisições pro serviço via rede interna do Docker Compose (`clickup-notfy:5000`), que não fica mais exposto diretamente ao host.

Configuração do Caddy fica num `Caddyfile` na raiz do projeto - uma única diretiva (`reverse_proxy`), sem necessidade de configuração manual de certificado.

**Pré-requisito operacional (fora do escopo do código)**: antes de subir o `docker-compose.prod.yml`, é necessário criar o registro DNS tipo A apontando o domínio escolhido (ex: `notify.cmmsistemas.com.br`) pro IP fixo do servidor, e liberar as portas 80/443 no firewall. Sem isso, o Caddy não consegue completar o desafio ACME do Let's Encrypt.

**Dois arquivos de compose, não um só com profiles**: `docker-compose.yml` (dev local, porta 5000 exposta direto, sem proxy) e `docker-compose.prod.yml` (produção, com Caddy) ficam separados. Mais simples de ler e rodar (`docker compose -f docker-compose.prod.yml up -d --build`) do que um único arquivo com profiles condicionais pra um projeto deste tamanho.

## Consequências
- Depois de trocar de ambiente (dev → produção), o endpoint do webhook cadastrado no ClickUp precisa ser atualizado uma última vez pra URL definitiva (`https://<DOMAIN>/webhooks/clickup`) — depois disso, fica estável (diferente do túnel, que exigia atualizar a cada queda/reinício).
- O volume `clickup_notfy_dados` (SQLite) e os volumes do Caddy (`caddy_dados`, `caddy_config` — certificados emitidos) são nomeados e persistem entre `docker compose down`/`up`, mas seriam perdidos num `docker compose down -v` acidental — mesma ressalva já válida pro dev local.
- Se no futuro for necessário rodar atrás de um proxy/CDN corporativo existente em vez do Caddy (ex: um Nginx já usado por outros serviços da empresa), essa ADR fica desatualizada nesse ponto e precisa ser revisada — a decisão aqui assume que este é o primeiro serviço exposto nesse domínio/porta.

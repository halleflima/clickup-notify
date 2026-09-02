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

**Porta 443 externa indisponível (caso real, servidor atrás de pfSense)**: no servidor de produção alvo, o time de infra confirmou que a porta 443 do IP público compartilhado ("IP quente") já está em uso por outro serviço via NAT — não dá pra fazer `IPQUENTE:443 → IPFRIO:443` como o cenário padrão assume. Duas consequências:
- **Porta externa alternativa**: a infra vai mapear uma porta diferente (ex: `IPQUENTE:8443 → IPFRIO:443`). Internamente o Caddy continua ouvindo na porta 443 padrão — só muda a porta que o mundo externo usa pra alcançar o domínio, então a URL do webhook cadastrada no ClickUp precisa incluir essa porta (`https://<DOMAIN>:8443/webhooks/clickup`).
- **Desafio HTTP-01 fica inviável**: como a porta 80 externa provavelmente tem a mesma limitação (mesmo IP compartilhado), o Caddy não consegue usar o método padrão de validação do Let's Encrypt (que depende de receber uma requisição HTTP na porta 80/443 padrão vinda dos servidores do Let's Encrypt). A alternativa é o **desafio DNS-01** (Caddy cria um registro TXT temporário no DNS do domínio pra provar posse, sem depender de nenhuma porta aberta pra isso).

**Pendente de confirmação com a infra**: qual serviço hospeda o DNS do domínio da empresa (Cloudflare, Registro.br, outro). Isso decide qual plugin de DNS o Caddy precisa (a imagem oficial `caddy:2-alpine` não inclui nenhum — seria necessário compilar uma imagem customizada via `xcaddy` com o módulo do provedor certo, ex: `github.com/caddy-dns/cloudflare`). Enquanto isso não for confirmado, o `Caddyfile`/`docker-compose.prod.yml` deste repositório continuam assumindo o cenário padrão (portas 80/443 livres, desafio HTTP-01 automático) — ajustar assim que a infra responder.

## Consequências
- Depois de trocar de ambiente (dev → produção), o endpoint do webhook cadastrado no ClickUp precisa ser atualizado uma última vez pra URL definitiva (`https://<DOMAIN>/webhooks/clickup`, ou `https://<DOMAIN>:<porta>/webhooks/clickup` se a porta 443 externa não estiver disponível) — depois disso, fica estável (diferente do túnel, que exigia atualizar a cada queda/reinício).
- O volume `clickup_notfy_dados` (SQLite) e os volumes do Caddy (`caddy_dados`, `caddy_config` — certificados emitidos) são nomeados e persistem entre `docker compose down`/`up`, mas seriam perdidos num `docker compose down -v` acidental — mesma ressalva já válida pro dev local.
- Se no futuro for necessário rodar atrás de um proxy/CDN corporativo existente em vez do Caddy (ex: um Nginx já usado por outros serviços da empresa), essa ADR fica desatualizada nesse ponto e precisa ser revisada — a decisão aqui assume que este é o primeiro serviço exposto nesse domínio/porta.
- Se a infra confirmar que a porta 443 externa está mesmo indisponível, essa ADR precisa de uma revisão pra registrar o provedor de DNS escolhido e o módulo do Caddy correspondente, assim que definido.

## Revisado: túnel supervisionado + atualização automática do endpoint

**Contexto da revisão**: a tentativa de abrir portas externas diretamente no roteador da empresa (Mikrotik RB750) causou uma queda de rede real durante a tentativa de configuração - decisão consciente de continuar com o túnel por enquanto, em vez de insistir em expor porta diretamente, até a infra resolver isso com mais segurança (ex: usando Safe Mode do RouterOS). O túnel (`cloudflared tunnel --url`, "quick tunnel" sem conta) permanece a solução usada, mas com duas lacunas identificadas em produção:
1. O processo do `cloudflared` rodava solto (`nohup`, sem supervisão) - se caísse de verdade (não só uma conexão individual falhando), ficava morto até alguém notar e subir na mão.
2. "Quick tunnel" não tem identidade fixa: toda vez que o processo reinicia do zero, o Cloudflare atribui uma **URL aleatória nova**. Se o processo caísse e alguém (ou uma automação) só o reiniciasse, o webhook cadastrado no ClickUp ficaria apontando pra URL antiga, quebrado - trocando um tipo de silêncio operacional por outro.

**Decisão**: `deploy/cloudflared/` (Dockerfile + `entrypoint.py`, biblioteca padrão do Python, sem dependências) sobe o `cloudflared` dentro de um container com `restart: unless-stopped` (via `docker-compose.tunnel.yml`, overlay opcional sobre o `docker-compose.yml` de dev) e observa a saída em busca da URL pública nova. Assim que aparece, chama a API do ClickUp (`PUT /v2/webhook/{id}` com o novo `endpoint`) automaticamente - sem esperar ninguém perceber que a URL mudou.

**Email de recuperação** (reaproveitando `EMAILS_ALERTA_OPERACIONAL` e as variáveis de SMTP do ADR-0011, já presentes no `.env`): depois de atualizar o endpoint com sucesso, o script também manda um email avisando que o túnel reiniciou e o endpoint foi atualizado sozinho - sem isso, uma recuperação automática bem-sucedida passava despercebida (só aparecia no `docker logs`), o que dificulta perceber que o túnel andou instável o suficiente pra derrubar o processo. Se todas as tentativas de atualizar o endpoint falharem, também manda um email diferente, pedindo ação manual. Reimplementado localmente (não importa `clickup_notfy.notificacoes.email_sender`) pelo mesmo motivo de manter esse container sem dependência do pacote principal - só duplica a lógica mínima de envio via `smtplib`.

**Nota sobre reconexões transitórias**: essa troca de URL só acontece quando o processo do `cloudflared` morre de verdade (o container reinicia do zero). Quedas de rede breves entre o `cloudflared` e a borda da Cloudflare são resolvidas pelo próprio `cloudflared` internamente (reconexão automática, sem matar o processo nem trocar de URL) - não há necessidade de nenhum temporizador de espera artificial antes de considerar o túnel "caído": o próprio processo continuar vivo já é o sinal de que a queda foi transitória.

Continua fora do pacote `clickup_notfy` (`src/`) de propósito, mesma decisão original desta ADR: é ferramenta operacional do ambiente onde o túnel é usado, não lógica de negócio do serviço - por isso não tem suíte de testes automatizados como o resto do projeto, e o script foi mantido deliberadamente simples (regex numa linha de log, uma chamada HTTP) pra minimizar superfície de erro.

### Consequências
- Fecha o ciclo completo: processo caiu → sobe sozinho → nova URL detectada → ClickUp atualizado sozinho, sem intervenção manual em nenhuma etapa.
- Continua expondo o serviço via infraestrutura de terceiro sem garantia de uptime (mesma ressalva já registrada sobre o túnel) - essa automação reduz o tempo de indisponibilidade em cada incidente, não elimina a causa raiz (a real solução de longo prazo continua sendo a exposição direta via domínio próprio, quando a infra resolver com segurança).
- Só **detecta** a URL nova uma vez por sessão do processo `cloudflared` (ela não muda de novo enquanto o mesmo processo continuar rodando) - reinícios adicionais dentro da mesma sessão de container não geram novas tentativas.
- **Achado real no primeiro deploy desta automação**: a primeira tentativa de `PUT` no endpoint falhou com `400 "Specified URL not allowed" (OAUTH_194)`, mesmo com a URL nova já respondendo normalmente - o ClickUp parece validar a URL de forma inconsistente/instável no exato momento do registro. Repetir a mesma chamada poucos segundos depois funcionou sem nenhuma mudança. Por isso `atualizar_endpoint_webhook_com_retry` tenta até 8 vezes, com 20s de intervalo, antes de desistir - a chamada é idempotente (mesmo valor reenviado), então repetir é seguro. Se mesmo assim esgotar as tentativas, o cenário fica coberto pelo alerta operacional (ADR-0011) na próxima verificação periódica de saúde do webhook, que detecta o endpoint desatualizado pelas falhas de entrega resultantes (`fail_count` alto).

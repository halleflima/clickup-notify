# clickup-notfy

Microserviço que traduz eventos do ClickUp em notificações por email, redirecionando para o email corporativo oficial de cada colaborador — já que as contas de convidado no ClickUp usam email pessoal, não o `@empresa.com`.

As decisões de arquitetura por trás desse projeto estão documentadas em [docs/adr](docs/adr/README.md).

## Rotas

| Método | Rota | O que faz | Autenticação |
|---|---|---|---|
| `GET` | `/` | Retorna a descrição de todas as rotas da API em JSON (essa própria lista, gerada em runtime). | Nenhuma |
| `POST` | `/webhooks/clickup` | Recebe os eventos do webhook do ClickUp (`taskCreated`, `taskStatusUpdated`, `taskCommentPosted`, `taskAssigneeUpdated`) e dispara as notificações por email. | Assinatura HMAC-SHA256 no header `X-Signature` |
| `POST` | `/mapeamentos-email` | Cadastra manualmente um mapeamento `clickup_user_id` → email oficial. | Bearer token |
| `GET` | `/mapeamentos-email` | Lista os mapeamentos cadastrados (aceita `?ativo=true` para filtrar). | Bearer token |
| `GET` | `/mapeamentos-email/<clickup_user_id>` | Detalha um mapeamento específico. | Bearer token |
| `PATCH` | `/mapeamentos-email/<clickup_user_id>` | Atualiza um mapeamento (ex: corrigir o email oficial, ou desativar com `ativo: false`). | Bearer token |

O `GET /` sempre reflete a versão mais atual dessa lista — se algo aqui ficar desatualizado, ele é a fonte de verdade.

## Rodando localmente

```bash
poetry install
poetry run python -m clickup_notfy.app
```

Ou via Docker:

```bash
docker compose up --build
```

As variáveis de ambiente necessárias estão listadas em [.env.example](.env.example).

## Deploy em produção

Pensado pra rodar num servidor da empresa com IP público fixo (ver [ADR-0010](docs/adr/0010-deploy-em-producao.md)) — sem depender de túnel, diferente do ambiente de teste local.

**Antes de subir:**
1. Copie `.env.example` para `.env` e preencha com os valores reais (SMTP, token do ClickUp, etc).
2. Preencha `DOMAIN` no `.env` com o domínio público que vai apontar pra esse servidor (ex: `notify.cmmsistemas.com.br`).
3. Crie o registro DNS tipo A desse domínio pro IP fixo do servidor.
4. Libere as portas 80 e 443 no firewall do servidor.

**Subindo:**

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Isso sobe dois containers: o serviço em si (só acessível internamente) e um Caddy na frente, cuidando do HTTPS automaticamente (certificado Let's Encrypt, emitido e renovado sozinho a partir do `DOMAIN`).

**Depois de subir**, cadastre (ou atualize) o webhook no ClickUp apontando para `https://<DOMAIN>/webhooks/clickup`.

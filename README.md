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

Pensado pra rodar num servidor da empresa com IP público fixo (ver [ADR-0010](docs/adr/0010-deploy-em-producao.md)) — sem depender de túnel, diferente do ambiente de teste local. Guia abaixo assume acesso via SSH a um servidor Linux (Debian/Ubuntu).

### 1. Pré-requisitos fora do servidor

- Registro DNS tipo A do domínio escolhido (ex: `notify.cmmsistemas.com.br`) apontando pro IP fixo do servidor.
- Portas 80 e 443 liberadas no firewall (necessárias pro Caddy emitir o certificado HTTPS).

### 2. Conectar e instalar o Docker (se ainda não tiver)

```bash
ssh usuario@ip-do-servidor

curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Depois do `usermod`, saia e entre de novo na sessão SSH pra o grupo `docker` valer (evita precisar de `sudo` em todo comando `docker`).

### 3. Clonar o repositório

O repositório é privado — use uma chave SSH cadastrada na sua conta do GitHub (ou um token de acesso, se preferir HTTPS):

```bash
git clone git@github.com:halleflima/clickup-notify.git
cd clickup-notify
```

### 4. Configurar o `.env`

```bash
cp .env.example .env
nano .env
```

Preencha com os valores reais: `CLICKUP_WEBHOOK_SECRET`, `CLICKUP_API_TOKEN`, `API_BEARER_TOKEN`, dados de `SMTP_*`, `EMAIL_REMETENTE`, `FALLBACK_EMAIL`, e o `DOMAIN` (o mesmo domínio do passo 1).

### 5. Subir a aplicação

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Isso sobe dois containers: o serviço em si (só acessível internamente) e um Caddy na frente, cuidando do HTTPS automaticamente (certificado Let's Encrypt, emitido e renovado sozinho a partir do `DOMAIN`).

### 6. Verificar se subiu certo

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Procure por uma linha do Caddy tipo `certificate obtained successfully` (pode levar alguns segundos). Depois, de fora do servidor:

```bash
curl -I https://<DOMAIN>/
```

Um `HTTP/2 200` confirma que o HTTPS está funcionando.

### 7. Cadastrar o webhook no ClickUp

Aponte (ou atualize, se já existir um) o webhook no ClickUp para `https://<DOMAIN>/webhooks/clickup`, usando o mesmo `CLICKUP_WEBHOOK_SECRET` configurado no `.env`.

### Atualizando uma versão já em produção

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

O volume do banco (`clickup_notfy_dados`) e os certificados do Caddy (`caddy_dados`, `caddy_config`) persistem entre subidas — só seriam apagados com um `docker compose down -v` explícito.

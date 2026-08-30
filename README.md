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

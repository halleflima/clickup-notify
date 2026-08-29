# ADR-0003: Mapeamento de identidade ClickUp → email oficial

## Status
Aceito

## Contexto
Contas de convidado no ClickUp usam email pessoal, diferente do email oficial `@empresa.com` de cada colaborador. Esse de/para muda ao longo do tempo (pessoas entram, saem, trocam de conta) e precisa ser gerenciável sem depender de deploy — descartada a opção de um arquivo JSON editado manualmente em favor de uma tabela gerenciada por API, já que o serviço já usa SQLite.

## Decisão
Tabela `mapeamentos_email` com os campos:

| Campo | Tipo | Observação |
|---|---|---|
| `clickup_user_id` | chave primária | ID do usuário no ClickUp — escolhido como chave em vez do email por ser estável (o email pode mudar, o ID não) |
| `clickup_email` | texto | email de convidado usado no ClickUp, campo informativo |
| `official_email` | texto | email corporativo oficial para onde a notificação é redirecionada |
| `nome` | texto | nome de exibição |
| `ativo` | booleano | permite desativar um mapeamento sem apagar o histórico (ex: colaborador trocou de conta) |
| `created_at` / `updated_at` | timestamp | auditoria básica |

Gerenciamento via rotas de API REST (CRUD: criar, listar, atualizar, desativar), protegidas por autenticação (ver [ADR-0005](0005-autenticacao-da-api-de-gerenciamento.md)).

Quando um evento do ClickUp referencia um `clickup_user_id` sem mapeamento ativo cadastrado, o comportamento de fallback está definido em [ADR-0004](0004-modelo-de-envio-outbox-retry-e-retencao.md).

## Consequências
- Cadastro precisa de disciplina manual: quando alguém entra, sai ou troca de conta no ClickUp, o mapeamento deve ser atualizado via API.
- Resolver o mapeamento por ID (em vez de email) exige que os eventos recebidos do webhook sempre tragam o ID do usuário do ClickUp — confirmado como disponível no payload.

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

**Auto-cadastro no primeiro evento (bootstrap sem script à parte)**: em vez de exigir que alguém cadastre manualmente todo o time antes de começar a usar o serviço, quando um destinatário resolvido (responsável, solicitante, ou atribuição) não tem nenhum registro em `mapeamentos_email`, o serviço cria automaticamente um mapeamento usando o email e o nome que a própria API do ClickUp devolve (`assignees[].email`/`username`, ou o mesmo campo dentro do custom field "Solicitante") — com `official_email` = mesmo email do ClickUp, como placeholder. Isso não piora nada (é exatamente pra onde a notificação iria antes de existir esse serviço), só evita bloquear o fluxo por falta de cadastro. A pessoa que administra o serviço então usa `GET /mapeamentos-email` pra ver quem foi auto-cadastrado e corrige o `official_email` de cada um via `PATCH /mapeamentos-email/<id>` conforme for confirmando quem é quem.

Esse auto-cadastro só acontece quando **não existe registro algum** para aquele `clickup_user_id` — se o registro existe mas está com `ativo: false` (alguém desativado deliberadamente, ex: saiu da empresa), o serviço não reativa sozinho; cai no fallback normal (ADR-0004). Também só é possível quando a fonte do evento tem o email disponível (chamadas que passam pela API de tarefa do ClickUp) — no evento `taskAssigneeUpdated`, cujo formato exato de `before`/`after` ainda não foi confirmado em produção, se o email não vier disponível, cai no fallback em vez de criar um mapeamento incompleto.

## Consequências
- Reduz o trabalho de bootstrap inicial: o time vai sendo cadastrado sozinho conforme os primeiros eventos chegam, sem precisar de um script de importação em massa.
- Ainda depende de disciplina manual para *corrigir* o `official_email` de cada auto-cadastro (o placeholder é só o email pessoal do ClickUp, o mesmo problema que o serviço existe pra resolver) e para lidar com saída/troca de conta de alguém.
- Resolver o mapeamento por ID (em vez de email) exige que os eventos recebidos do webhook sempre tragam o ID do usuário do ClickUp — confirmado como disponível no payload.

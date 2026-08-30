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

**Auto-cadastro no primeiro evento (bootstrap sem script à parte)**: em vez de exigir que alguém cadastre manualmente todo o time antes de começar a usar o serviço, o serviço cria automaticamente um mapeamento usando o email e o nome que a própria API do ClickUp devolve (`assignees[].email`/`username`, o mesmo campo dentro do custom field "Solicitante", ou o objeto pessoa de `before`/`after` do `taskAssigneeUpdated`) — com `official_email` = mesmo email do ClickUp, como placeholder. Isso não piora nada (é exatamente pra onde a notificação iria antes de existir esse serviço), só evita bloquear o fluxo por falta de cadastro. A pessoa que administra o serviço então usa `GET /mapeamentos-email` pra ver quem foi auto-cadastrado e corrige o `official_email` de cada um via `PATCH /mapeamentos-email/<id>` conforme for confirmando quem é quem.

**Revisado**: o auto-cadastro roda para **toda pessoa que aparece no evento** (todo `responsável` + `solicitante` da tarefa, ou todo `before`/`after` de uma atribuição), independentemente de essa pessoa vir a ser efetivamente notificada — inclusive quando a regra de supressão por ator (ADR-0002) zera a lista de destinatários (ex: alguém muda o status do próprio chamado e ninguém mais está envolvido). Motivo: mesmo um evento que não notifica ninguém ainda revela quem são os responsáveis/solicitantes reais de um chamado, então cadastramos essa informação de qualquer forma — o time vai ficando conhecido no `GET /mapeamentos-email` aos poucos, não só através de quem já recebeu email. Fica de fora desse cadastro automático apenas o **autor da ação em si**, quando ele não é também responsável/solicitante da tarefa — o payload do webhook só traz o ID do autor, não o email dele, e buscar isso exigiria uma chamada adicional (lista de membros do workspace) fora de escopo por ora.

Esse auto-cadastro só acontece quando **não existe registro algum** para aquele `clickup_user_id` — se o registro existe mas está com `ativo: false` (alguém desativado deliberadamente, ex: saiu da empresa), o serviço não reativa sozinho; cai no fallback normal (ADR-0004). Também só é possível quando a fonte do evento tem o email disponível.

## Consequências
- Reduz o trabalho de bootstrap inicial: o time vai sendo cadastrado sozinho conforme os primeiros eventos chegam, sem precisar de um script de importação em massa — inclusive em eventos que não geram notificação pra ninguém.
- Ainda depende de disciplina manual para *corrigir* o `official_email` de cada auto-cadastro (o placeholder é só o email pessoal do ClickUp, o mesmo problema que o serviço existe pra resolver) e para lidar com saída/troca de conta de alguém.
- Resolver o mapeamento por ID (em vez de email) exige que os eventos recebidos do webhook sempre tragam o ID do usuário do ClickUp — confirmado como disponível no payload.
- O autor de uma ação só é auto-cadastrado se também aparecer como responsável ou solicitante da tarefa — do contrário, fica de fora até aparecer em outro evento nesse papel.

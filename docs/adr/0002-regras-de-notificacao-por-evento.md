# ADR-0002: Regras de notificação por tipo de evento

## Status
Aceito

## Contexto
O ClickUp pode emitir um grande número de tipos de evento via webhook. Notificar em cima de todos eles geraria spam e reduziria a atenção real às notificações que importam. Foi necessário restringir o escopo a quatro tipos de evento e definir, para cada um, quem recebe a notificação.

Na configuração real do webhook (feita pela interface do ClickUp), selecionar "todos os eventos" resulta em `events: []` na resposta da API — ou seja, mesmo tendo decidido notificar só 4 tipos, o webhook pode acabar inscrito em *todos* os eventos do workspace (criação/exclusão de lista, pasta, espaço, meta, etc.). O código não pode assumir que só vai receber os 4 tipos que nos interessam.

O campo "solicitante" de um chamado no ClickUp é um campo obrigatório do tipo pessoa (person picker) — ou seja, referencia um usuário real do ClickUp com um ID, da mesma forma que o campo "responsável" (assignee). Isso permite resolver o solicitante pela mesma lógica de ID usada para o responsável (ver [ADR-0003](0003-mapeamento-de-identidade-clickup-email.md)).

## Decisão
Eventos monitorados nesta fase e suas regras de notificação:

1. **Chamado criado**
   - Notifica sempre o solicitante.
   - Notifica o responsável somente se já houver alguém atribuído no momento da criação.

2. **Novo comentário adicionado**
   - Notifica todos os envolvidos (responsável e solicitante).
   - Exceção: o autor do comentário nunca é notificado do próprio comentário.
   - Conteúdo do email é propositalmente minimalista (ex: "novo comentário adicionado no chamado X"), sem trecho do comentário — o objetivo é forçar o usuário a entrar no ClickUp para gerenciar o chamado, não substituir a ferramenta.

3. **Mudança de status** (ex: entrar em "a fazer", "desenvolvimento", "bloqueado")
   - Notifica responsável e solicitante.
   - Regra simétrica de supressão por ator: quem executou a própria mudança de status não é notificado dela. Se foi o responsável quem mudou, ele não recebe; se foi o solicitante, o mesmo vale para ele.
   - O conteúdo do email mostra explicitamente o status anterior e o novo (ex: "o chamado X foi alterado de Em Desenvolvimento para Testes"), extraídos de `history_items[].before`/`.after` (ver [ADR-0006](0006-seguranca-do-webhook-e-idempotencia.md)).
   - O formato do email é único e padrão para qualquer transição de status. Existe um campo opcional de **observação** no template, preenchido a partir de um dicionário simples hardcoded no código (ex: `{"reanálise": "este chamado precisa ser analisado, por favor acesse o ClickUp"}`), não uma tabela no banco — hoje só 1-2 status (ex: "reanálise", possivelmente "bloqueado") precisam desse texto extra, e uma tabela com CRUD seria estrutura demais pra esse volume. Quando não há observação mapeada para o status em questão, o campo simplesmente não aparece no email — o formato do email nunca muda, só o conteúdo desse bloco opcional. Se essa lista crescer ou precisar ser editada por alguém sem acesso ao código, migrar para uma tabela (mesmo padrão do `mapeamentos_email`) é uma extensão simples, sem mudar o template.
   - A granularidade exata dos status que disparam notificação (todos os status vs. só alguns) fica aberta para refinamento futuro.

4. **Responsável atribuído ou removido de um chamado já existente** (`taskAssigneeUpdated`)
   - Ao adicionar um responsável: notifica só a pessoa recém-atribuída (ex: "você foi atribuído ao chamado X"). O solicitante não é notificado nesse evento (já é coberto pelas notificações de status).
   - Ao remover um responsável: notifica a pessoa removida (ex: "você foi desvinculado do chamado X").
   - Mesma regra simétrica de supressão por ator: se alguém se auto-atribui ou se auto-remove, não recebe notificação da própria ação.
   - ClickUp permite múltiplos responsáveis por tarefa; se uma única mudança adicionar e/ou remover mais de uma pessoa, é enviada uma notificação individual por pessoa afetada (não uma notificação agregada por chamado).

Cada tipo de evento usa um template de email genérico comum, com um bloco de conteúdo que varia por tipo de evento — não templates totalmente independentes por evento (ver [ADR-0004](0004-modelo-de-envio-outbox-retry-e-retencao.md) para o mecanismo de envio).

**Filtro de segurança contra eventos fora do escopo**: `regras.EVENTOS_SUPORTADOS` lista os 4 tipos acima. Qualquer evento recebido fora dessa lista (ex: `folderCreated`, `spaceDeleted`, `goalUpdated`) é ignorado antes de qualquer chamada à API do ClickUp ou tentativa de montar notificação — a requisição do webhook ainda responde 200 normalmente, só não gera nenhum outbox. Isso é necessário como camada de defesa mesmo com o webhook do ClickUp configurado só para os 4 eventos, porque a interface do ClickUp representa "todos os eventos" como `events: []` na API (é fácil cadastrar o webhook errado sem perceber), e também protege contra o ClickUp adicionar novos tipos de evento no futuro.

**Identificador do chamado usado no email**: o ClickUp tem um ID interno alfanumérico (ex: `86ak870jk`) e, opcionalmente, um "Custom Task ID" legível configurável por workspace (ex: `DV-8165`, campo `custom_id` na API — pode vir `null` se a funcionalidade não estiver habilitada). O email sempre usa o `custom_id` quando disponível, caindo para o ID bruto só se não houver. Isso só é possível para os 3 eventos que buscam a tarefa completa (criação, comentário, status) — o `taskAssigneeUpdated` não busca a tarefa (ver acima) e por isso sempre usa o ID bruto do ClickUp no email, mesmo quando a tarefa tem um `custom_id` configurado.

## Consequências
- Fácil de estender para outros eventos ou sub-casos de status no futuro, sem mudar a arquitetura de envio.
- Depende de o campo "solicitante" continuar sendo um person picker no ClickUp; se isso mudar (ex: virar campo de texto livre), a resolução por ID deixa de funcionar e precisa ser revisitada.
- Eventos fora do escopo nunca geram chamada à API do ClickUp nem notificação — o custo de processá-los é desprezível (uma checagem de conjunto).
- Emails de atribuição (`taskAssigneeUpdated`) mostram o ID bruto do ClickUp em vez do `custom_id` legível — inconsistência conhecida e aceita, para não reintroduzir uma chamada à API nesse evento só por causa da exibição.

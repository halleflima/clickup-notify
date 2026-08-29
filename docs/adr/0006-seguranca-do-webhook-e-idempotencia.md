# ADR-0006: Segurança do webhook e idempotência de eventos

## Status
Aceito

## Contexto
O serviço expõe um endpoint público (via container Docker no servidor da empresa) para receber eventos via webhook do ClickUp. Já existe um webhook configurado no workspace, mas com outro propósito/chave — será criado um webhook dedicado para esta solução. Como qualquer endpoint público, ele está sujeito a requisições forjadas. Além disso, o próprio ClickUp pode reentregar (retry) um evento já enviado se o serviço não responder a tempo, o que pode gerar notificação duplicada se não tratado.

## Decisão
- Será criado um **webhook dedicado** no ClickUp via `POST /v2/team/{team_id}/webhook` (não reaproveitando o já existente com outra chave/propósito), inscrito nos eventos: `taskCreated`, `taskStatusUpdated`, `taskCommentPosted`, `taskAssigneeUpdated` (ver [ADR-0002](0002-regras-de-notificacao-por-evento.md)). Sem filtro de `space_id`/`folder_id`/`list_id`/`task_id` — o webhook cobre o workspace (team) inteiro.
- A resposta da criação retorna um `secret`, que deve ser guardado só em variável de ambiente (nunca em código ou banco em texto puro sem necessidade).
- Toda requisição recebida no endpoint do webhook tem sua assinatura validada **antes** de qualquer processamento; requisições sem assinatura válida são rejeitadas com HTTP 401, sem tocar no banco.
- Cada mudança dentro de um evento carrega um ID próprio (`history_items[].id`, ver seção técnica abaixo). Antes de processar cada item, o serviço verifica se aquele ID já foi registrado em `notificacoes_enviadas` — se sim, é descartado sem gerar novo envio (idempotência).

## Detalhes técnicos (levantados na documentação oficial do ClickUp)

**Validação de assinatura:**
- Header: `X-Signature`.
- Algoritmo: HMAC-SHA256 sobre o **corpo bruto (raw bytes) da requisição**, usando o `secret` do webhook como chave, resultado em hexadecimal.
- Importante: o hash deve ser calculado sobre os bytes exatos recebidos, antes de qualquer parse/re-serialização do JSON pelo Flask — recalcular a partir de um `json.dumps()` do corpo já parseado pode gerar um hash diferente (ordem de chaves/espaçamento) e rejeitar requisições legítimas.

**Estrutura do payload recebido (POST no nosso endpoint):**
```json
{
  "event": "taskStatusUpdated",
  "webhook_id": "uuid-do-webhook",
  "task_id": "abc123",
  "history_items": [
    {
      "id": "uuid-do-item-de-historico",
      "type": 1,
      "date": "1234567890",
      "user": { "id": 123, "username": "fulano" },
      "before": "valor_anterior",
      "after": "valor_novo"
    }
  ]
}
```
- `history_items` é um **array** — uma única requisição pode trazer mais de uma mudança. O processamento deve iterar cada item, tratando cada `history_items[].id` como a chave de deduplicação (não existe um "evento_id" único de topo — a menção a `evento_id` no [ADR-0004](0004-modelo-de-envio-outbox-retry-e-retencao.md) se refere a esse `history_items[].id`).
- `history_items[].user` é quem executou a ação — é o campo usado na regra de supressão por ator (ADR-0002).
- `task_id` identifica o chamado/tarefa.

**Resposta ao ClickUp:** a documentação pública não detalha o status esperado nem a política de retry, mas a listagem de webhooks expõe um campo `health` com `fail_count` — indício de que falhas repetidas de entrega podem levar o ClickUp a considerar o webhook degradado (e possivelmente desativá-lo). Por segurança, o endpoint deve responder **200 rapidamente** (validar assinatura, gravar o evento como pendente, retornar) e processar o envio de fato de forma assíncrona/no scheduler — evitar qualquer lógica lenta (SMTP, etc.) no caminho síncrono da requisição.

## Consequências
- Reduz o risco de notificações falsas disparadas por requisições forjadas.
- Elimina duplicidade de notificação em caso de retry do próprio ClickUp, tratando a deduplicação no nível correto (`history_items[].id`, não um ID de topo inexistente).
- Responder rápido e processar de forma assíncrona evita que o webhook seja marcado como degradado/desativado pelo ClickUp em picos de lentidão do envio de email.

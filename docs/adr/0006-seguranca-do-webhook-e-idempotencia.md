# ADR-0006: Segurança do webhook e idempotência de eventos

## Status
Aceito

## Contexto
O serviço expõe um endpoint público (via container Docker no servidor da empresa) para receber eventos via webhook do ClickUp. Já existe um webhook configurado no workspace, mas com outro propósito/chave — será criado um webhook dedicado para esta solução. Como qualquer endpoint público, ele está sujeito a requisições forjadas. Além disso, o próprio ClickUp pode reentregar (retry) um evento já enviado se o serviço não responder a tempo, o que pode gerar notificação duplicada se não tratado.

## Decisão
- Será criado um **webhook dedicado** no ClickUp via `POST /v2/team/{team_id}/webhook` (não reaproveitando o já existente com outra chave/propósito), inscrito nos eventos: `taskCreated`, `taskStatusUpdated`, `taskCommentPosted`, `taskAssigneeUpdated` (ver [ADR-0002](0002-regras-de-notificacao-por-evento.md)). Sem filtro de `space_id`/`folder_id`/`list_id`/`task_id` — o webhook cobre o workspace (team) inteiro.
- A resposta da criação retorna um `secret`, que deve ser guardado só em variável de ambiente (nunca em código ou banco em texto puro sem necessidade).
- Toda requisição recebida no endpoint do webhook tem sua assinatura validada **antes** de qualquer processamento; requisições sem assinatura válida são rejeitadas com HTTP 401, sem tocar no banco.
- Cada mudança dentro de um evento carrega um ID próprio (`history_items[].id`, ver seção técnica abaixo). Antes de processar cada item, o serviço verifica se aquele ID já foi registrado em `eventos_processados` — se sim, é descartado sem gerar novo envio (idempotência).
- **Importante (revisado ao implementar o PR de outbox)**: o registro em `eventos_processados` só acontece **depois** que a resolução de destinatários for concluída com sucesso (chamada à API do ClickUp incluída) — não no momento em que o item é recebido. Se essa resolução falhar (ex: API do ClickUp fora do ar), o evento não é marcado como tratado e a rota responde HTTP 502; o próprio mecanismo de retry do webhook do ClickUp reentrega a requisição depois, e como o evento nunca foi marcado como processado, ele é tentado de novo do zero. Uma falha *só* no envio SMTP (depois que os destinatários já foram resolvidos) não afeta esse dedup — fica registrada como pendente em `notificacoes_enviadas` e é responsabilidade do scheduler de retry (ADR-0004).

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

**Resposta ao ClickUp:** a documentação pública não detalha o status esperado nem a política de retry, mas a listagem de webhooks expõe um campo `health` com `fail_count` — indício de que falhas repetidas de entrega podem levar o ClickUp a considerar o webhook degradado (e possivelmente desativá-lo). A intenção original era responder 200 rapidamente e processar tudo de forma assíncrona; na implementação optamos por manter o processamento síncrono (sem thread/fila separada, dado o baixo volume esperado — poucas centenas de eventos/dia), aceitando que uma chamada lenta à API do ClickUp ou ao SMTP atrase a resposta ocasionalmente. Isso é considerado aceitável porque: (1) o volume é baixo, (2) timeouts curtos (10s) limitam o pior caso, e (3) se a resolução de destinatários falhar e o ClickUp reentregar por timeout, o dedup ainda protege contra duplicidade seguindo a regra acima. Se isso se mostrar um problema real (ex: ClickUp marcando o webhook como degradado), revisitar com processamento em background thread.

## Consequências
- Reduz o risco de notificações falsas disparadas por requisições forjadas.
- Elimina duplicidade de notificação em caso de retry do próprio ClickUp, tratando a deduplicação no nível correto (`history_items[].id`, não um ID de topo inexistente) e só depois que o processamento é bem-sucedido.
- Processamento síncrono é mais simples de implementar e testar, ao custo de uma latência de resposta ocasionalmente maior — trade-off deliberado dado o volume baixo, revisitável se necessário.

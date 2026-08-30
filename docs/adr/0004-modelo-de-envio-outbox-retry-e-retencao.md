# ADR-0004: Modelo de envio — outbox, retry e retenção

## Status
Aceito

## Contexto
O envio de email será via SMTP básico usando uma conta do Google Workspace da empresa (inicialmente uma conta pessoal para testes, futuramente `notificacao@empresa` ou similar). O limite conhecido é de ~2.000 emails/24h por usuário do Workspace; o volume esperado é de ~300-400/dia — folga grande, mas o serviço precisa lidar com falha de envio (SMTP fora do ar, ou no caso extremo de atingir a cota) sem perder notificações.

Também foi levantada a necessidade futura de rastrear se um email foi aberto (para identificar contas do ClickUp não utilizadas ou pessoas que não leem as notificações), mas essa funcionalidade não será implementada agora — só o espaço no schema é reservado.

## Decisão

### Tabela única (outbox + log + espaço para tracking futuro)
`notificacoes_enviadas`:

| Campo | Observação |
|---|---|
| `id` | chave primária |
| `evento_id` | ID do item de mudança do ClickUp (`history_items[].id` — um único POST de webhook pode trazer vários itens), usado para deduplicação (ver [ADR-0006](0006-seguranca-do-webhook-e-idempotencia.md)) |
| `task_id` | ID bruto do chamado no ClickUp — usado na proteção contra duplicata por conteúdo (ver abaixo) |
| `destinatario_email` | email oficial de destino |
| `tipo_evento` | criação / comentário / mudança de status |
| `status` | `pendente` \| `enviado` \| `falha` |
| `tentativas` | contador de tentativas de envio |
| `enviado_em` | timestamp do envio bem-sucedido |
| `aberto` | booleano, reservado para tracking futuro de abertura (pixel) — não implementado nesta fase |
| `aberto_em` | timestamp, idem |
| `created_at` | timestamp de criação do registro |

### Estratégia de envio e retry
1. Ao processar um evento, tenta enviar o email imediatamente.
2. Se falhar, o registro fica com `status = pendente`.
3. Um scheduler embutido no processo (APScheduler) roda a cada 5 minutos e tenta reenviar tudo que está `pendente`, em ordem do mais antigo para o mais novo.

Essa combinação (tentativa imediata + varredura periódica) cobre tanto falha temporária de SMTP quanto o cenário em que o serviço fica sem eventos novos chegando por um tempo — o que uma estratégia puramente "reenviar a cada N eventos novos" não cobriria.

### Retenção e limpeza (purge)
Rotina diária (parte do mesmo scheduler) apaga registros de `notificacoes_enviadas` com `created_at` anterior a **2 anos**, via `DELETE ... WHERE created_at < now() - 2 anos`. Um índice em `created_at` mantém a operação barata. Um `VACUUM` mensal (não diário) devolve ao disco o espaço liberado pelas exclusões, evitando o custo de reescrever o banco inteiro com frequência desnecessária.

Rejeitada a alternativa de um job mensal que calcula "qual mês checar" — o purge diário simples com filtro de data é equivalente e mais simples de implementar/entender.

### Proteção contra duplicata por conteúdo (achado em produção)
Confirmado testando de verdade: o ClickUp às vezes emite **dois `history_items` com IDs diferentes** para uma única ação real do usuário (ex: 2 eventos `taskCreated`, poucos segundos um do outro, para a criação de um único chamado). Como os IDs são genuinamente diferentes, a deduplicação por `evento_id` (ADR-0006) não pega esse caso — cada um é processado normalmente e geraria um email duplicado.

Antes de criar um novo registro em `notificacoes_enviadas`, o serviço verifica se já existe um envio **bem-sucedido** com o mesmo `task_id` + `tipo_evento` + `destinatario_email` + `corpo` (conteúdo idêntico, não só o tipo) nos últimos 5 minutos (`outbox_repository.ja_enviada_recentemente`). Se sim, a notificação é descartada silenciosamente (só um log informativo).

Comparar o **conteúdo renderizado**, não só o tipo de evento, é deliberado: duas mudanças de status genuinamente diferentes (ex: A→B, depois B→C minutos depois) têm corpos diferentes e não são suprimidas — só bloqueia repetição de fato idêntica. Só considera envios com `status = 'enviado'` — uma tentativa que falhou não bloqueia a próxima.

### Fallback para usuário sem mapeamento
Se um evento referenciar um `clickup_user_id` sem mapeamento ativo em `mapeamentos_email`, o serviço loga o erro e envia a notificação para um email de fallback único, fixo via variável de ambiente.

## Considerado e adiado
- **Tracking real de abertura de email** (pixel de rastreamento): o campo `aberto`/`aberto_em` já existe no schema, mas a lógica de marcação não será implementada agora.
- **Múltiplos emails de fallback por área/coordenação** (ex: notificar o coordenador quando um subordinado não está recebendo email): adiado até que o custo/necessidade justifique — o fallback único cobre o caso de erro básico por enquanto.

## Consequências
- Nenhuma notificação é perdida silenciosamente: toda falha vira um registro `pendente` que será reprocessado.
- A tabela cresce de forma limitada (purge de 2 anos), mantendo o banco leve indefinidamente.
- Evoluir para tracking de abertura ou fallback múltiplo no futuro não exige migração de schema — só ativar a lógica que já tem onde guardar o dado.
- A proteção por conteúdo cobre o caso confirmado (ClickUp duplicando `history_items` para uma mesma ação), mas depende de o conteúdo ser realmente idêntico — se algo no corpo variar entre as duas emissões (ex: timestamp diferente no rodapé), a duplicata não seria pega. Não é o caso hoje (o "Atualizado em" vem do `history_items[].date`, que é o mesmo nos dois eventos duplicados observados).

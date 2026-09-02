# ADR-0011: Alerta operacional para problemas no próprio serviço

## Status
Aceito

## Contexto
Em produção, dois incidentes reais no mesmo dia expuseram uma lacuna: o serviço não tinha nenhum jeito de avisar quem o administra quando **ele próprio** está com problema (diferente de uma notificação normal de chamado).

1. **Bug de parsing não tratado**: `taskStatusUpdated` quebrou com `AttributeError: 'dict' object has no attribute 'strip'` porque o ClickUp manda `before`/`after` de status como objeto, não string (corrigido separadamente, ver commit `66e5865`). O endpoint respondeu `502` repetidamente.
2. **Webhook suspenso silenciosamente**: os `502` repetidos acumularam falhas no lado do ClickUp até o campo `health.fail_count` chegar a **101**, e o ClickUp **suspendeu o webhook automaticamente** (`health.status: suspended`). A partir daí, nenhum evento novo chegou mais ao serviço - sem nenhum aviso, silenciosamente, até alguém notar que notificações pararam de chegar e investigar manualmente via API do ClickUp.

O ADR-0004 já tinha cogitado e adiado a ideia de múltiplos emails de fallback por área/coordenação (seção Considerado e adiado), mas com outro propósito (avisar um coordenador quando um subordinado específico não está recebendo notificação de chamado). O que falta aqui é diferente: um canal separado para avisar sobre **saúde do serviço em si**, não sobre um chamado específico.

## Decisão

### Canal separado, não uma extensão do FALLBACK_EMAIL
`FALLBACK_EMAIL` (ADR-0004) continua exatamente como está - é o destino de uma notificação normal de chamado quando falta mapeamento de destinatário. Alerta operacional é conceitualmente diferente (avisa sobre o serviço, não sobre um chamado) e usa uma variável própria: `EMAILS_ALERTA_OPERACIONAL`, lista separada por vírgula, suportando um ou mais destinatários. Vazio desativa o recurso sem afetar o resto do serviço.

### Dois gatilhos

1. **Falha não tratada ao processar um evento** (`webhook/routes.py`, mesmo ponto que já loga e responde `502`): dispara um alerta com o `evento_id`, tipo de evento e `task_id` afetados, avisando que o ClickUp deve reentregar automaticamente e que os logs têm o traceback completo.

2. **Webhook do ClickUp perto do limite de falhas** (`scheduler.py`, novo job `verificar_saude_webhook`, intervalo de 15 minutos): consulta `GET /team/{team_id}/webhook` e olha o campo `health` do webhook configurado (identificado por `CLICKUP_TEAM_ID` + `CLICKUP_WEBHOOK_ID`, novas variáveis - sem elas, esse gatilho específico fica desativado, mas o gatilho 1 continua funcionando normalmente). Dispara alerta quando `fail_count >= LIMITE_FAIL_COUNT_ALERTA` (padrão **20**) ou quando `status == suspended`.

   **O limite de 20 é uma estimativa conservadora, não um valor oficial do ClickUp** - a documentação pública não publica a partir de quantas falhas o webhook é suspenso. O incidente real observado teve suspensão em `fail_count=101`; 20 dá uma margem grande pra reagir bem antes disso. Se se mostrar cedo ou tarde demais na prática, é só ajustar via variável de ambiente, sem precisar de deploy de código.

### Cooldown por tipo de alerta (evita spam)
Cada envio de alerta é registrado numa tabela nova, `alertas_operacionais` (`tipo`, `enviado_em`). Antes de enviar, o serviço checa se já mandou um alerta do mesmo `tipo` nas últimas **6 horas** - se sim, suprime (só loga). Isso cobre dois cenários que sem cooldown virariam flood de email:
- Uma rajada de eventos falhando um atrás do outro (gatilho 1 rodaria a cada evento).
- O job de saúde do webhook rodando a cada 15 minutos enquanto o problema não é corrigido (gatilho 2 rodaria dezenas de vezes por dia).

O cooldown é **por tipo**, não global - uma falha de processamento e um webhook degradado ao mesmo tempo geram alertas independentes, cada um com seu próprio cooldown.

Deliberadamente **não** é alerta só uma vez até o problema ser resolvido (o que exigiria detectar quando o problema se resolveu, mais complexo) - é alerta de novo a cada 6h enquanto persistir. Mais simples de implementar e testar, com o trade-off de até 6h de atraso pra um segundo aviso do mesmo problema.

### Envio best-effort, nunca bloqueia o fluxo principal
O envio do alerta (`notificacoes/alerta_operacional.py`) nunca propaga exceção pro chamador - uma falha ao enviar o alerta em si vira só um log. Isso é obrigatório no gatilho 1: ele roda dentro do `except` que já está tratando uma falha; se o envio do alerta também falhasse sem tratamento, mascararia o erro original e potencialmente quebraria a resposta `502` que o ClickUp depende para saber que precisa reentregar.

### Conteúdo do alerta
Texto simples (não usa o template HTML do ADR-0009, que é para notificação de chamado) - só um bloco monoespaçado com a mensagem, escapado via `html.escape` por padrão de segurança (mesmo sendo texto que o próprio serviço monta, não input externo direto).

## Consequências
- Dá visibilidade a exatamente os dois cenários que já aconteceram de verdade em produção, sem esperar alguém notar manualmente que notificações pararam.
- Novas variáveis de ambiente (`EMAILS_ALERTA_OPERACIONAL`, `CLICKUP_TEAM_ID`, `CLICKUP_WEBHOOK_ID`, `LIMITE_FAIL_COUNT_ALERTA`) são todas opcionais - o serviço continua funcionando sem elas configuradas, só sem esse recurso.
- Novo job no scheduler (5 minutos → 15 minutos de intervalo) adiciona uma chamada periódica à API do ClickUp; volume desprezível frente ao limite de rate da API.
- O limite de `fail_count` sendo uma estimativa (não documentado oficialmente pelo ClickUp) é uma fragilidade conhecida - fica configurável via variável de ambiente exatamente por isso.
- Não cobre ainda o caso de detectar quando o problema foi resolvido (ex: enviar um voltou ao normal) - fica em aberto para uma extensão futura, se a necessidade justificar.

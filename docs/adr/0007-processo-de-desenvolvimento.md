# ADR-0007: Processo de desenvolvimento — testes e tamanho de PR

## Status
Aceito

## Contexto
Definição de convenções de processo para a construção deste microserviço, à parte das decisões de arquitetura em si.

## Decisão
- **Testes automatizados** (pytest) são obrigatórios para as regras de negócio mais sujeitas a erro silencioso: supressão de notificação por ator (quem executou a ação não é notificado dela), dedup de evento por `evento_id`, resolução de responsável/solicitante via ID do ClickUp, e a lógica de retry/purge da tabela `notificacoes_enviadas`.
- **Tamanho de Pull Request**: no máximo **500 linhas de código efetivo** por PR. Comentários e testes não contam para esse limite.

## Consequências
- A implementação será fatiada em PRs menores e sequenciais em vez de um único PR monolítico, por exemplo: (1) recebimento de webhook + validação + dedup, (2) CRUD de mapeamento + autenticação, (3) outbox + retry de envio, (4) purge + testes complementares.
- Facilita revisão e reduz risco de regressão por mudança grande demais de uma vez só.

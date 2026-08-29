# ADRs — clickup-notfy

Registro das decisões de arquitetura tomadas para o microserviço de notificação que traduz eventos do ClickUp (contas de convidado, com email pessoal) para o email corporativo oficial de cada colaborador.

O Movidesk (sistema de atendimento ao cliente) está fora de escopo nesta fase — o serviço trata apenas do fluxo ClickUp (nível de desenvolvimento).

| ADR | Título |
|---|---|
| [0001](0001-visao-geral-e-stack.md) | Visão geral e stack tecnológica |
| [0002](0002-regras-de-notificacao-por-evento.md) | Regras de notificação por tipo de evento |
| [0003](0003-mapeamento-de-identidade-clickup-email.md) | Mapeamento de identidade ClickUp → email oficial |
| [0004](0004-modelo-de-envio-outbox-retry-e-retencao.md) | Modelo de envio: outbox, retry e retenção |
| [0005](0005-autenticacao-da-api-de-gerenciamento.md) | Autenticação da API de gerenciamento |
| [0006](0006-seguranca-do-webhook-e-idempotencia.md) | Segurança do webhook e idempotência de eventos |
| [0007](0007-processo-de-desenvolvimento.md) | Processo de desenvolvimento: testes e tamanho de PR |

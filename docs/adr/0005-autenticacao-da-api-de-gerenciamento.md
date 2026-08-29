# ADR-0005: Autenticação da API de gerenciamento

## Status
Aceito

## Contexto
As rotas de CRUD do mapeamento de identidade (ver [ADR-0003](0003-mapeamento-de-identidade-clickup-email.md)) lidam com dados sensíveis (email pessoal x corporativo de colaboradores) e precisam de alguma proteção. Foram avaliadas três opções ao longo da discussão: nenhuma autenticação, um token Bearer estático simples, e um esquema completo de JWT com tabela de usuários. A opção de JWT completo chegou a ser considerada, mas foi revertida ao se confirmar que só uma pessoa (o responsável pelo serviço) vai acessar essa API depois de configurada — construir login, expiração e tabela de usuários para um único operador seria complexidade sem retorno.

## Decisão
Autenticação via **Bearer token estático**, definido por variável de ambiente, validado em middleware nas rotas da API de mapeamento. Sem tabela de usuários, sem JWT, sem expiração de token.

## Consequências
- Simples de implementar e operar (poucas linhas de código).
- Se no futuro mais de uma pessoa precisar acessar a API com controle de permissão por usuário, essa decisão deve ser revisitada — não é tratada como definitiva para sempre, só suficiente para o cenário atual de operador único.

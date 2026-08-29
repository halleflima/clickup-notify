# ADR-0001: Visão geral e stack tecnológica

## Status
Aceito

## Contexto
A empresa usa dois sistemas de gerenciamento de chamados: Movidesk (atendimento ao cliente) e ClickUp (nível de desenvolvimento). Para cortar custos, os colaboradores acessam o ClickUp com contas de convidado usando email pessoal (ex: `hallefempresa@gmail.com`), diferente do email corporativo oficial (ex: `hallef@empresa.com`). Isso quebra qualquer notificação nativa do ClickUp que dependa do email da conta, já que ninguém lê aquele email pessoal no dia a dia.

O Movidesk foi conscientemente deixado fora do escopo desta fase — o problema a resolver agora é só o fluxo ClickUp.

## Decisão
Construir um microserviço em Python com Flask, gerenciamento de dependências via Poetry, empacotado como imagem Docker para deploy no servidor próprio da empresa (self-hosted, não SaaS/cloud de terceiros). Persistência em SQLite, por ser leve o suficiente para o volume esperado (algumas centenas de eventos/notificações por dia) e não exigir um servidor de banco separado.

## Consequências
- Deploy simples (um container, um arquivo de banco).
- Se o volume crescer muito ou for necessário rodar múltiplas réplicas simultâneas do serviço, o SQLite pode virar gargalo de concorrência de escrita — reavaliar migração para Postgres/MySQL se isso acontecer.
- Sem dependência de infraestrutura externa (fila, cache, banco gerenciado) nesta fase.

# ADR-0012: Suporte a múltiplos solicitantes por chamado

## Status
Aceito

## Contexto
Investigando uma dúvida ("o campo Solicitante hoje trata mais de um solicitante por chamado?"), foi encontrada uma lacuna real no código: o campo "Solicitante" do ClickUp é um person picker (ver [ADR-0002](0002-regras-de-notificacao-por-evento.md)) que **suporta selecionar mais de uma pessoa**, exatamente como o campo "Responsável" já suporta e já é tratado corretamente (\`extrair_responsaveis\` sempre devolveu uma lista).

O código já reconhecia, em comentário, que o campo pode vir como lista do ClickUp:

```python
def _normalizar_valor_pessoa(valor) -> dict | None:
    """O campo de pessoa do ClickUp pode vir como lista (person picker) ou objeto unico."""
    if isinstance(valor, list):
        return valor[0] if valor else None  # <- so o primeiro, o resto e descartado
    ...
```

Mas pegava só `valor[0]` — o primeiro solicitante da lista — e **descartava silenciosamente** qualquer outro, sem log, sem erro. Na prática: um chamado aberto com 2+ solicitantes só notificava o primeiro; os demais nunca recebiam nenhuma notificação de nenhum evento, e nunca eram auto-cadastrados em \`mapeamentos_email\` (ADR-0003) só por causa disso.

Essa lacuna não era uma decisão documentada em nenhum ADR anterior — o ADR-0002 e o ADR-0003 sempre descrevem "o solicitante" no singular, sem tratar explicitamente o caso de múltiplos. Foi uma omissão, não uma escolha consciente.

## Decisão
Tratar "solicitante" no plural em toda a cadeia, no mesmo padrão que "responsável" já usa:

- \`clickup_api.py\`: \`extrair_solicitante\`/\`extrair_solicitante_id\` (singular) viram \`extrair_solicitantes\`/\`extrair_solicitantes_ids\` (plural, sempre retornam lista — vazia se não houver ninguém). \`_normalizar_valor_pessoa\` vira \`_normalizar_valores_pessoa\`, mantendo todas as pessoas da lista em vez de só a primeira.
- \`notificacoes/regras.py\`: \`resolver_destinatarios_criacao\` e \`resolver_destinatarios_envolvidos\` passam a receber \`solicitantes_ids: list[int]\` em vez de \`solicitante_id: int | None\`. Todo solicitante da lista é notificado igualmente (mesmo papel \`"solicitante"\`/\`"envolvido"\`), incluindo a supressão por ator já existente (se um dos solicitantes for quem executou a ação, só ele é suprimido — os outros continuam sendo notificados normalmente).
- \`notificacoes/processador.py\`: propaga a lista de solicitantes pros metadados (\`solicitante_nome\`, que já usava \`_nomes_ou\` — a mesma função que junta múltiplos responsáveis com vírgula — então o email já sabia mostrar vários nomes, só nunca recebia mais de um solicitante pra mostrar) e pro auto-cadastro em \`mapeamentos_email\` (cada solicitante da lista passa a ser conhecido, não só o primeiro).

Nenhuma mudança foi necessária em \`notificacoes/conteudo.py\` nem no template de email (ADR-0009) — o texto "Solicitante" no email já era uma junção de nomes via \`_nomes_ou\`, preparada pra múltiplos valores desde que existia pra responsável. A lacuna estava inteiramente na extração de dados do ClickUp, não na exibição.

## Consequências
- Um chamado com múltiplos solicitantes agora notifica todos eles em cada evento aplicável (criação, comentário, mudança de status), na mesma regra que já vale pra responsáveis.
- Todos os solicitantes de um chamado passam a ser auto-cadastrados em \`mapeamentos_email\` (ADR-0003), não só o primeiro — o time fica conhecido mais rápido.
- Nenhuma mudança de schema de banco ou de contrato de API externa (\`/mapeamentos-email\`) foi necessária — a mudança é inteiramente interna à resolução de destinatários.
- Assinatura pública de \`resolver_destinatarios_criacao\`/\`resolver_destinatarios_envolvidos\` muda de \`int | None\` pra \`list[int]\` — quebra de compatibilidade se algo externo chamasse essas funções diretamente, mas elas são só usadas internamente por \`processador.py\`, atualizado junto neste mesmo PR.

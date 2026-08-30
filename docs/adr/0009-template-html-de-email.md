# ADR-0009: Template HTML de email

## Status
Aceito

## Contexto
Os emails de notificação eram texto puro (`MIMEText` simples), sem identidade visual. O usuário pediu um template visual e trouxe um design pronto (feito no Claude Design): um único layout HTML genérico, compatível com clientes de email (tabelas, estilo inline, preheader, responsivo), com blocos opcionais que aparecem ou desaparecem conforme o tipo de evento.

## Decisão

**Motor de template**: Jinja2 (já vem como dependência transitiva do Flask, adicionado aqui como dependência direta) renderizando um arquivo `notificacoes/templates/email.html.jinja2`. O arquivo é basicamente o HTML do design original, com `{% if %}` adicionados nos dois blocos opcionais:
- **Bloco de alteração** (de → para): aparece em mudança de status e em atribuição/remoção de responsável; ausente na criação e no comentário.
- **Bloco de texto livre**: aparece na criação (descrição do solicitante) e na mudança de status (observação hardcoded por status, ver abaixo); ausente no comentário (ver ADR-0002) e na atribuição.

**Conteúdo por tipo de evento** (`conteudo.py`, funções `_contexto_*`):
- **Criação**: descrição varia conforme já haver responsável ou não; mostra a descrição do solicitante quando disponível (campo já vem de graça na mesma busca de tarefa, sem chamada extra) — diferente do comentário, que continua sem mostrar conteúdo (decisão reafirmada, ver ADR-0002).
- **Status**: bloco de alteração mostra o `before`/`after` do próprio evento. Reaproveita o dicionário hardcoded de observação por status (`OBSERVACOES_POR_STATUS`, já existente desde o ADR-0002) no bloco de texto livre — não é uma feature nova, só passou a ter um lugar visual pra aparecer.
- **Atribuição/remoção**: como o antes/depois do próprio evento normalmente só tem uma ponta preenchida (ex: alguém foi adicionado, sem indicar quem estava lá antes), o bloco de alteração usa o nome do próprio destinatário como uma das pontas (`Não atribuído → {nome}` ao ser atribuído; `{nome} → Não atribuído` ao ser removido) — é a representação fiel do que os dados realmente contêm, sem inventar uma "pessoa anterior" que não temos como saber.

**Cor de destaque por status**: dicionário `_CORES_POR_STATUS` (hoje só `"encerrado": "#2f8f5b"`, verde; todo o resto usa o azul padrão `#3E7CB1`), no mesmo padrão hardcoded do `OBSERVACOES_POR_STATUS` — status exatos confirmados com o usuário (print da configuração de status do ClickUp do workspace).

**Logo**: inicialmente mantido como texto estilizado ("CMM" / "CMM Sistemas de Informação"), não uma imagem — email não carrega imagem de arquivo local (precisa de URL pública), e não havia onde hospedar. **Revisado**: o usuário já tem a logo hospedada no próprio site institucional (`https://cmmsistemas.com.br/wp-content/uploads/2022/06/logo-cmm.png`), então o cabeçalho passou a usar essa imagem remota via `<img>` (`EMPRESA_LOGO_URL` em `conteudo.py`), como o design original já sugeria em comentário. Trade-off aceito: por ser uma imagem remota (não embutida nos bytes do email), alguns clientes de email (Outlook principalmente) podem bloquear o carregamento até o usuário liberar manualmente — comportamento padrão da maioria dos clientes de email para remetentes ainda não conhecidos, não é uma falha do template.

**Rodapé sem links de autoatendimento**: o design original tinha "Gerenciar notificações" e "Cancelar inscrição", apontando pra páginas que não existem no sistema. Removidos por ora (link quebrado não é aceitável em produção) — telemetria/preferências de notificação viram melhoria futura, registrada em issue separada no GitHub, não nesta implementação.

**Envio como HTML puro** (não multipart com fallback texto): `email_sender.py` manda `MIMEText(corpo_html, "html", "utf-8")` diretamente, sem uma versão em texto puro alternativa. Simplificação deliberada — a grande maioria dos clientes de email modernos renderiza HTML sem problema, e manter duas versões do conteúdo sincronizadas adicionaria complexidade desproporcional ao tamanho do projeto.

**Data do evento**: `history_items[].date` (epoch em milissegundos, como string) passou a ser extraído no parser (`data_epoch_ms`) e formatado como `DD/MM/AAAA às HH:MM`. Se ausente ou inválido, usa o momento atual como aproximação.

## Consequências
- O outbox (`notificacoes_enviadas.corpo`) agora guarda HTML renderizado em vez de texto puro — sem mudança de schema, é a mesma coluna `TEXT`; o retry reenvia o HTML já pronto, sem re-renderizar.
- Qualquer alteração visual futura é só editar o arquivo `.jinja2` — não precisa mexer em `conteudo.py`, a menos que mude o conjunto de variáveis.
- Emails de comentário continuam minimalistas por decisão consciente (ADR-0002) — o design comporta mostrar o texto do comentário, mas isso ficou fora de escopo porque exigiria uma chamada nova à API (`GET /task/{id}/comment`).
- Sem fallback em texto puro: destinatários com clientes de email muito antigos ou que desabilitam HTML veem uma caixa de entrada com HTML cru — risco aceito dado o público (colaboradores internos usando clientes de email modernos).

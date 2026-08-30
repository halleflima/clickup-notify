# ADR-0008: Rota de documentação da API

## Status
Aceito

## Contexto
A API cresceu (webhook, CRUD de mapeamento) sem nenhuma forma de consulta rápida de quais rotas existem, qual autenticação cada uma exige e qual o formato esperado de corpo/resposta. Gerar isso automaticamente (Swagger/OpenAPI) tem um custo de setup e manutenção desproporcional ao tamanho atual do projeto.

## Decisão
Rota pública `GET /` retorna um JSON com a lista de rotas conhecidas — método, caminho, descrição, autenticação exigida, corpo de requisição esperado (quando houver) e possíveis respostas. O conteúdo vem de uma lista Python mantida à mão em `clickup_notfy/documentacao/rotas.py`, **não é gerada a partir das rotas reais do Flask**.

Essa rota não exige autenticação (`Bearer` ou assinatura) — é só descrição de formato, sem dado sensível.

## Consequências
- Zero dependência nova, zero geração automática — mas exige disciplina manual: toda vez que uma rota for criada/alterada, `rotas.py` precisa ser atualizado à mão, ou a documentação fica desatualizada silenciosamente.
- Serve como referência rápida (`curl http://host/`) sem precisar abrir o código-fonte.
- Se o número de rotas crescer muito ou a divergência entre a lista e o código real virar um problema recorrente, vale reconsiderar uma geração automática (ex: Flask-Smorest, apispec) — não é o caso hoje.

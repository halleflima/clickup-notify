import requests

BASE_URL = "https://api.clickup.com/api/v2"
NOME_CAMPO_SOLICITANTE = "Solicitante"


def buscar_tarefa(task_id: str, token: str) -> dict:
    resposta = requests.get(
        f"{BASE_URL}/task/{task_id}",
        headers={"Authorization": token},
        timeout=10,
    )
    resposta.raise_for_status()
    return resposta.json()


def _pessoa(bruto: dict) -> dict:
    return {"id": bruto["id"], "email": bruto.get("email"), "nome": bruto.get("username")}


def extrair_responsaveis(tarefa: dict) -> list[dict]:
    return [_pessoa(assignee) for assignee in tarefa.get("assignees", [])]


def extrair_responsaveis_ids(tarefa: dict) -> list[int]:
    return [responsavel["id"] for responsavel in extrair_responsaveis(tarefa)]


def _buscar_custom_field(tarefa: dict, nome_campo: str) -> dict | None:
    """Casa pelo nome do campo de forma tolerante: no ClickUp real, campos
    customizados costumam ter emoji/prefixo no nome (ex: "👨‍⚖️ Solicitante"),
    entao uma comparacao exata nunca bate. Usa "contem", sem diferenciar
    maiusculas/minusculas."""
    nome_procurado = nome_campo.casefold()
    for campo in tarefa.get("custom_fields", []):
        if nome_procurado in (campo.get("name") or "").casefold():
            return campo
    return None


def _normalizar_valor_pessoa(valor) -> dict | None:
    """O campo de pessoa do ClickUp pode vir como lista (person picker) ou objeto unico."""
    if isinstance(valor, list):
        return valor[0] if valor else None
    if isinstance(valor, dict):
        return valor
    return None


def extrair_solicitante(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> dict | None:
    campo = _buscar_custom_field(tarefa, nome_campo)
    if campo is None:
        return None

    bruto = _normalizar_valor_pessoa(campo.get("value"))
    if bruto is None:
        return None

    return _pessoa(bruto)


def extrair_solicitante_id(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> int | None:
    solicitante = extrair_solicitante(tarefa, nome_campo)
    return solicitante["id"] if solicitante else None


_PRIORIDADE_EM_PORTUGUES = {"urgent": "Urgente", "high": "Alta", "normal": "Normal", "low": "Baixa"}


def extrair_prioridade(tarefa: dict) -> str | None:
    prioridade = tarefa.get("priority")
    if not prioridade:
        return None
    chave = (prioridade.get("priority") or "").casefold()
    return _PRIORIDADE_EM_PORTUGUES.get(chave)


def extrair_status_atual(tarefa: dict) -> str | None:
    return (tarefa.get("status") or {}).get("status")


def extrair_descricao(tarefa: dict) -> str | None:
    return tarefa.get("text_content") or tarefa.get("description") or None


def extrair_nome_tarefa(tarefa: dict) -> str | None:
    return tarefa.get("name")

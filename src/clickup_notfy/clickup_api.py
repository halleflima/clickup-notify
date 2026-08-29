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
    return [pessoa["id"] for pessoa in extrair_responsaveis(tarefa)]


def extrair_solicitante(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> dict | None:
    campo = next(
        (c for c in tarefa.get("custom_fields", []) if c.get("name") == nome_campo), None
    )
    if campo is None:
        return None

    valor = campo.get("value")
    if isinstance(valor, list):
        bruto = valor[0] if valor else None
    elif isinstance(valor, dict):
        bruto = valor
    else:
        bruto = None

    return _pessoa(bruto) if bruto else None


def extrair_solicitante_id(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> int | None:
    solicitante = extrair_solicitante(tarefa, nome_campo)
    return solicitante["id"] if solicitante else None

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


def extrair_responsaveis_ids(tarefa: dict) -> list[int]:
    return [assignee["id"] for assignee in tarefa.get("assignees", [])]


def extrair_solicitante_id(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> int | None:
    campo = next(
        (c for c in tarefa.get("custom_fields", []) if c.get("name") == nome_campo), None
    )
    if campo is None:
        return None

    valor = campo.get("value")
    if isinstance(valor, list):
        return valor[0]["id"] if valor else None
    if isinstance(valor, dict):
        return valor.get("id")
    return None

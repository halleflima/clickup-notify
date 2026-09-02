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


def _normalizar_valores_pessoa(valor) -> list[dict]:
    """O campo de pessoa do ClickUp pode vir como lista (person picker com
    mais de uma pessoa selecionada) ou objeto unico (uma so pessoa) -
    normaliza os dois formatos pra sempre devolver uma lista, sem descartar
    ninguem quando ha mais de uma pessoa (ver ADR-0012)."""
    if isinstance(valor, list):
        return [item for item in valor if isinstance(item, dict)]
    if isinstance(valor, dict):
        return [valor]
    return []


def extrair_solicitantes(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> list[dict]:
    campo = _buscar_custom_field(tarefa, nome_campo)
    if campo is None:
        return []

    return [_pessoa(bruto) for bruto in _normalizar_valores_pessoa(campo.get("value"))]


def extrair_solicitantes_ids(tarefa: dict, nome_campo: str = NOME_CAMPO_SOLICITANTE) -> list[int]:
    return [solicitante["id"] for solicitante in extrair_solicitantes(tarefa, nome_campo)]


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

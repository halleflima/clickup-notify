from typing import Any


def extrair_itens_historico(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza o payload do webhook do ClickUp numa lista de itens de mudanca.

    Um unico POST pode trazer varios `history_items`, cada um com seu proprio
    `id` (usado para deduplicacao) e seu proprio autor da acao.
    """
    tipo_evento = payload.get("event")
    task_id = payload.get("task_id")
    itens_historico = payload.get("history_items", [])

    itens_normalizados = []
    for item in itens_historico:
        usuario = item.get("user") or {}
        itens_normalizados.append(
            {
                "id": item.get("id"),
                "tipo_evento": tipo_evento,
                "task_id": task_id,
                "autor_id": usuario.get("id"),
                "before": item.get("before"),
                "after": item.get("after"),
                "data_epoch_ms": item.get("date"),
            }
        )

    return itens_normalizados

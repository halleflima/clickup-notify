from typing import Any


def _normalizar_status(valor):
    """Confirmado em producao: em taskStatusUpdated o ClickUp manda o status
    como objeto ({"status": "...", "color": ...}), nao como string simples -
    usar direto quebra _contexto_status (AttributeError: 'dict' object has
    no attribute 'strip'). Mesma classe de problema ja tratada em
    processador._extrair_pessoas para taskAssigneeUpdated."""
    if isinstance(valor, dict):
        return valor.get("status")
    return valor


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
        before = item.get("before")
        after = item.get("after")

        if tipo_evento == "taskStatusUpdated":
            before = _normalizar_status(before)
            after = _normalizar_status(after)

        itens_normalizados.append(
            {
                "id": item.get("id"),
                "tipo_evento": tipo_evento,
                "task_id": task_id,
                "autor_id": usuario.get("id"),
                "before": before,
                "after": after,
                "data_epoch_ms": item.get("date"),
            }
        )

    return itens_normalizados

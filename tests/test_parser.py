from clickup_notfy.webhook.parser import extrair_itens_historico


def test_extrai_um_unico_item_de_historico():
    payload = {
        "event": "taskStatusUpdated",
        "task_id": "abc123",
        "history_items": [
            {
                "id": "hist-1",
                "user": {"id": 111, "username": "fulano"},
                "before": "em desenvolvimento",
                "after": "testes",
                "date": "1621915186877",
            }
        ],
    }

    itens = extrair_itens_historico(payload)

    assert itens == [
        {
            "id": "hist-1",
            "tipo_evento": "taskStatusUpdated",
            "task_id": "abc123",
            "autor_id": 111,
            "before": "em desenvolvimento",
            "after": "testes",
            "data_epoch_ms": "1621915186877",
        }
    ]


def test_extrai_multiplos_itens_de_um_unico_payload():
    payload = {
        "event": "taskAssigneeUpdated",
        "task_id": "abc123",
        "history_items": [
            {"id": "hist-1", "user": {"id": 111}, "before": None, "after": 222},
            {"id": "hist-2", "user": {"id": 111}, "before": 333, "after": None},
        ],
    }

    itens = extrair_itens_historico(payload)

    assert [item["id"] for item in itens] == ["hist-1", "hist-2"]


def test_payload_sem_history_items_retorna_lista_vazia():
    payload = {"event": "taskCreated", "task_id": "abc123"}

    assert extrair_itens_historico(payload) == []


def test_extrai_status_de_objeto_bruto_do_clickup():
    """Formato real confirmado em producao: before/after de taskStatusUpdated
    vem como objeto ({"status": "...", "color": ...}), nao string simples -
    usar direto quebra _contexto_status (AttributeError: 'dict' object has
    no attribute 'strip')."""
    payload = {
        "event": "taskStatusUpdated",
        "task_id": "abc123",
        "history_items": [
            {
                "id": "hist-1",
                "user": {"id": 111},
                "before": {"status": "em desenvolvimento", "color": "#000", "type": "custom"},
                "after": {"status": "testes", "color": "#111", "type": "custom"},
                "date": "1621915186877",
            }
        ],
    }

    itens = extrair_itens_historico(payload)

    assert itens[0]["before"] == "em desenvolvimento"
    assert itens[0]["after"] == "testes"


def test_extrai_status_none_permanece_none():
    payload = {
        "event": "taskStatusUpdated",
        "task_id": "abc123",
        "history_items": [
            {"id": "hist-1", "user": {"id": 111}, "before": None, "after": {"status": "aberto"}}
        ],
    }

    itens = extrair_itens_historico(payload)

    assert itens[0]["before"] is None
    assert itens[0]["after"] == "aberto"


def test_evento_diferente_de_status_nao_normaliza_before_after():
    """taskAssigneeUpdated ja tem sua propria normalizacao em
    processador._extrair_pessoas - o parser nao deve mexer nesses valores."""
    payload = {
        "event": "taskAssigneeUpdated",
        "task_id": "abc123",
        "history_items": [
            {"id": "hist-1", "user": {"id": 111}, "before": None, "after": {"id": 222, "username": "Ciclano"}}
        ],
    }

    itens = extrair_itens_historico(payload)

    assert itens[0]["after"] == {"id": 222, "username": "Ciclano"}

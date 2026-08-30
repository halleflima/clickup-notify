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

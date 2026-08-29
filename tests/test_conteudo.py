from clickup_notfy.notificacoes.conteudo import montar_assunto, montar_corpo


def test_assunto_por_tipo_de_evento():
    assert "abc123" in montar_assunto("taskCreated", "abc123")
    assert "abc123" in montar_assunto("evento_desconhecido", "abc123")


def test_corpo_criacao():
    assert "criado" in montar_corpo("taskCreated", "abc123", {})


def test_corpo_comentario_nao_revela_conteudo_do_comentario():
    corpo = montar_corpo("taskCommentPosted", "abc123", {})

    assert "abc123" in corpo
    assert "ClickUp" in corpo


def test_corpo_mudanca_de_status_mostra_antes_e_depois():
    corpo = montar_corpo("taskStatusUpdated", "abc123", {}, before="em desenvolvimento", after="testes")

    assert "em desenvolvimento" in corpo
    assert "testes" in corpo


def test_corpo_status_com_observacao_cadastrada():
    corpo = montar_corpo(
        "taskStatusUpdated", "abc123", {}, before="em desenvolvimento", after="reanálise"
    )

    assert "precisa ser analisado" in corpo


def test_corpo_status_sem_observacao_nao_adiciona_texto_extra():
    corpo = montar_corpo("taskStatusUpdated", "abc123", {}, before="a fazer", after="bloqueado")

    assert "precisa ser analisado" not in corpo


def test_corpo_atribuicao_adicionado():
    corpo = montar_corpo("taskAssigneeUpdated", "abc123", {"papel": "atribuido"})

    assert "atribuído" in corpo


def test_corpo_atribuicao_removido():
    corpo = montar_corpo("taskAssigneeUpdated", "abc123", {"papel": "removido"})

    assert "desvinculado" in corpo

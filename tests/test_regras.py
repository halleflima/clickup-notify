from clickup_notfy.notificacoes.regras import (
    resolver_destinatarios_atribuicao,
    resolver_destinatarios_criacao,
    resolver_destinatarios_envolvidos,
)


def por_id(destinatarios):
    return {d["clickup_user_id"] for d in destinatarios}


def test_criacao_notifica_solicitante_e_responsavel():
    destinatarios = resolver_destinatarios_criacao(solicitantes_ids=[1], responsaveis_ids=[2, 3])

    assert por_id(destinatarios) == {1, 2, 3}


def test_criacao_sem_responsavel_ainda_notifica_so_solicitante():
    destinatarios = resolver_destinatarios_criacao(solicitantes_ids=[1], responsaveis_ids=[])

    assert por_id(destinatarios) == {1}


def test_criacao_sem_solicitante_resolvido_nao_quebra():
    destinatarios = resolver_destinatarios_criacao(solicitantes_ids=[], responsaveis_ids=[2])

    assert por_id(destinatarios) == {2}


def test_criacao_notifica_todos_os_solicitantes_quando_ha_mais_de_um():
    """ADR-0012: um chamado pode ter mais de 1 solicitante - antes so o
    primeiro era notificado, os demais eram descartados silenciosamente."""
    destinatarios = resolver_destinatarios_criacao(solicitantes_ids=[1, 4], responsaveis_ids=[2])

    assert por_id(destinatarios) == {1, 2, 4}
    papeis = {d["clickup_user_id"]: d["papel"] for d in destinatarios}
    assert papeis[1] == "solicitante"
    assert papeis[4] == "solicitante"


def test_envolvidos_notifica_responsavel_e_solicitante_exceto_autor():
    destinatarios = resolver_destinatarios_envolvidos(
        autor_id=2, solicitantes_ids=[1], responsaveis_ids=[2, 3]
    )

    assert por_id(destinatarios) == {1, 3}


def test_envolvidos_autor_e_o_solicitante_e_suprimido():
    destinatarios = resolver_destinatarios_envolvidos(
        autor_id=1, solicitantes_ids=[1], responsaveis_ids=[2]
    )

    assert por_id(destinatarios) == {2}


def test_envolvidos_multiplos_responsaveis():
    destinatarios = resolver_destinatarios_envolvidos(
        autor_id=99, solicitantes_ids=[1], responsaveis_ids=[2, 3]
    )

    assert por_id(destinatarios) == {1, 2, 3}


def test_envolvidos_multiplos_solicitantes_um_deles_e_o_autor():
    """O autor e suprimido individualmente - os outros solicitantes
    continuam sendo notificados normalmente."""
    destinatarios = resolver_destinatarios_envolvidos(
        autor_id=1, solicitantes_ids=[1, 4], responsaveis_ids=[2]
    )

    assert por_id(destinatarios) == {2, 4}


def test_atribuicao_notifica_apenas_adicionado():
    destinatarios = resolver_destinatarios_atribuicao(
        autor_id=99, responsaveis_ids_antes=[], responsaveis_ids_depois=[2]
    )

    assert destinatarios == [{"clickup_user_id": 2, "papel": "atribuido"}]


def test_atribuicao_notifica_apenas_removido():
    destinatarios = resolver_destinatarios_atribuicao(
        autor_id=99, responsaveis_ids_antes=[2], responsaveis_ids_depois=[]
    )

    assert destinatarios == [{"clickup_user_id": 2, "papel": "removido"}]


def test_atribuicao_auto_atribuicao_nao_notifica_o_proprio_ator():
    destinatarios = resolver_destinatarios_atribuicao(
        autor_id=2, responsaveis_ids_antes=[], responsaveis_ids_depois=[2]
    )

    assert destinatarios == []


def test_atribuicao_adiciona_e_remove_ao_mesmo_tempo():
    destinatarios = resolver_destinatarios_atribuicao(
        autor_id=99, responsaveis_ids_antes=[2], responsaveis_ids_depois=[3]
    )

    assert {"clickup_user_id": 3, "papel": "atribuido"} in destinatarios
    assert {"clickup_user_id": 2, "papel": "removido"} in destinatarios
    assert len(destinatarios) == 2

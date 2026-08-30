from clickup_notfy.notificacoes.conteudo import montar_email, montar_variaveis_email

METADADOS_BASE = {
    "identificador": "DV-8165",
    "titulo": "Erro ao gerar boleto",
    "prioridade": "Alta",
    "descricao": None,
    "status_atual": "em desenvolvimento",
    "responsavel_nome": "Fulano",
    "solicitante_nome": "Ciclano",
}


def item_base(tipo_evento, **overrides):
    base = {
        "tipo_evento": tipo_evento,
        "task_id": "abc123",
        "autor_id": 999,
        "before": None,
        "after": None,
        "data_epoch_ms": None,
    }
    base.update(overrides)
    return base


def test_criacao_com_responsavel_usa_texto_generico():
    variaveis = montar_variaveis_email(item_base("taskCreated"), {}, METADADOS_BASE, "Marcos")

    assert variaveis["evento_tipo"] == "Novo chamado"
    assert "aberto" in variaveis["evento_titulo"].lower()
    assert "não tem responsável" not in variaveis["evento_descricao"]
    assert variaveis["alteracao_de"] is None


def test_criacao_sem_responsavel_avisa_que_falta_responsavel():
    metadados = dict(METADADOS_BASE, responsavel_nome="Não atribuído")

    variaveis = montar_variaveis_email(item_base("taskCreated"), {}, metadados, "Marcos")

    assert "não tem responsável" in variaveis["evento_descricao"]


def test_criacao_com_descricao_preenche_bloco_de_texto():
    metadados = dict(METADADOS_BASE, descricao="Erro 500 ao gerar boleto no fim de semana.")

    variaveis = montar_variaveis_email(item_base("taskCreated"), {}, metadados, "Marcos")

    assert variaveis["texto_label"] == "Descrição do solicitante"
    assert variaveis["texto_corpo"] == "Erro 500 ao gerar boleto no fim de semana."


def test_criacao_sem_descricao_nao_preenche_bloco_de_texto():
    variaveis = montar_variaveis_email(item_base("taskCreated"), {}, METADADOS_BASE, "Marcos")

    assert variaveis["texto_label"] is None
    assert variaveis["texto_corpo"] is None


def test_comentario_nao_revela_conteudo_do_comentario():
    variaveis = montar_variaveis_email(item_base("taskCommentPosted"), {}, METADADOS_BASE, "Marcos")

    assert variaveis["texto_corpo"] is None
    assert "DV-8165" in variaveis["evento_titulo"]


def test_status_mostra_de_e_para():
    item = item_base("taskStatusUpdated", before="Aberto", after="Em andamento")

    variaveis = montar_variaveis_email(item, {}, METADADOS_BASE, "Marcos")

    assert variaveis["alteracao_label"] == "Status"
    assert variaveis["alteracao_de"] == "Aberto"
    assert variaveis["alteracao_para"] == "Em andamento"
    assert "Aberto" in variaveis["evento_descricao"]
    assert "Em andamento" in variaveis["evento_descricao"]


def test_status_reanalise_preenche_observacao_generica():
    item = item_base("taskStatusUpdated", before="Em andamento", after="Reanálise")

    variaveis = montar_variaveis_email(item, {}, METADADOS_BASE, "Marcos")

    assert variaveis["texto_label"] == "Observação"
    assert "reanálise" in variaveis["texto_corpo"].lower()


def test_status_sem_observacao_configurada_fica_vazio():
    item = item_base("taskStatusUpdated", before="A fazer", after="Bloqueado")

    variaveis = montar_variaveis_email(item, {}, METADADOS_BASE, "Marcos")

    assert variaveis["texto_corpo"] is None


def test_status_encerrado_usa_cor_verde():
    item = item_base("taskStatusUpdated", before="Em andamento", after="Encerrado")
    metadados = dict(METADADOS_BASE, status_atual="Encerrado")

    variaveis = montar_variaveis_email(item, {}, metadados, "Marcos")

    assert variaveis["cor_evento"] == "#2f8f5b"


def test_status_normal_usa_cor_padrao():
    variaveis = montar_variaveis_email(item_base("taskStatusUpdated"), {}, METADADOS_BASE, "Marcos")

    assert variaveis["cor_evento"] == "#3E7CB1"


def test_atribuicao_adicionado_mostra_nome_do_destinatario_como_atual():
    item = item_base("taskAssigneeUpdated")
    destinatario = {"clickup_user_id": 111, "papel": "atribuido"}

    variaveis = montar_variaveis_email(item, destinatario, METADADOS_BASE, "Marcos")

    assert variaveis["alteracao_de"] == "Não atribuído"
    assert variaveis["alteracao_para"] == "Marcos"


def test_atribuicao_removido_mostra_nome_do_destinatario_como_anterior():
    item = item_base("taskAssigneeUpdated")
    destinatario = {"clickup_user_id": 111, "papel": "removido"}

    variaveis = montar_variaveis_email(item, destinatario, METADADOS_BASE, "Marcos")

    assert variaveis["alteracao_de"] == "Marcos"
    assert variaveis["alteracao_para"] == "Não atribuído"


def test_chamado_url_aponta_para_o_clickup():
    variaveis = montar_variaveis_email(item_base("taskCreated"), {}, METADADOS_BASE, "Marcos")

    assert variaveis["chamado_url"] == "https://app.clickup.com/t/abc123"


def test_montar_email_retorna_assunto_e_html_renderizado():
    assunto, corpo_html = montar_email(item_base("taskCreated"), {}, METADADOS_BASE, "Marcos")

    assert assunto == "Clickup | [DV-8165] Novo chamado"
    assert "<!DOCTYPE html>" in corpo_html
    assert "DV-8165" in corpo_html
    assert "Marcos" in corpo_html


def test_montar_email_omite_bloco_de_alteracao_quando_nao_ha():
    _, corpo_html = montar_email(item_base("taskCreated"), {}, METADADOS_BASE, "Marcos")

    assert "ANTERIOR" not in corpo_html


def test_montar_email_inclui_bloco_de_alteracao_na_mudanca_de_status():
    item = item_base("taskStatusUpdated", before="Aberto", after="Em andamento")

    _, corpo_html = montar_email(item, {}, METADADOS_BASE, "Marcos")

    assert "ANTERIOR" in corpo_html
    assert "Aberto" in corpo_html

import pytest
import responses

from clickup_notfy import db
from clickup_notfy.mapeamentos import repository as mapeamentos_repository
from clickup_notfy.notificacoes.processador import processar_evento, resolver_contexto_evento

CONFIG = {
    "CLICKUP_API_TOKEN": "pk_teste",
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "usuario",
    "SMTP_PASSWORD": "senha",
    "EMAIL_REMETENTE": "notificacao@empresa.com",
    "FALLBACK_EMAIL": "fallback@empresa.com",
}


@pytest.fixture
def conexao():
    conexao = db.conectar(":memory:")
    db.inicializar_schema(conexao)
    yield conexao
    conexao.close()


@pytest.fixture(autouse=True)
def sem_envio_real(monkeypatch):
    monkeypatch.setattr(
        "clickup_notfy.notificacoes.processador.email_sender.tentar_enviar", lambda *a, **k: True
    )


def item_criacao(evento_id="hist-1"):
    return {
        "id": evento_id,
        "tipo_evento": "taskCreated",
        "task_id": "abc123",
        "autor_id": 999,
        "before": None,
        "after": None,
    }


@responses.activate
def test_processa_criacao_usa_email_do_mapeamento(conexao):
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}]},
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert len(notificacoes) == 1
    assert notificacoes[0]["destinatario_email"] == "fulano@empresa.com"
    assert notificacoes[0]["status"] == "enviado"


@responses.activate
def test_processa_criacao_sem_mapeamento_e_sem_email_usa_fallback(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 999}}]},
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "fallback@empresa.com"


@responses.activate
def test_processa_criacao_sem_mapeamento_mas_com_email_auto_cadastra(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "assignees": [],
            "custom_fields": [
                {
                    "name": "Solicitante",
                    "value": {"id": 555, "username": "novato", "email": "novato@gmail.com"},
                }
            ],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "novato@gmail.com"

    mapeamento = mapeamentos_repository.buscar_por_id(conexao, 555)
    assert mapeamento["clickup_email"] == "novato@gmail.com"
    assert mapeamento["official_email"] == "novato@gmail.com"
    assert mapeamento["nome"] == "novato"
    assert mapeamento["ativo"] is True


@responses.activate
def test_processa_criacao_reusa_mapeamento_auto_cadastrado_na_segunda_vez(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "assignees": [],
            "custom_fields": [
                {
                    "name": "Solicitante",
                    "value": {"id": 555, "username": "novato", "email": "novato@gmail.com"},
                }
            ],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(evento_id="hist-1"), CONFIG)
    processar_evento(conexao, item_criacao(evento_id="hist-2"), CONFIG)

    mapeamentos = mapeamentos_repository.listar(conexao)
    assert len(mapeamentos) == 1


@responses.activate
def test_processa_criacao_mapeamento_inativo_usa_fallback(conexao):
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")
    mapeamentos_repository.atualizar(conexao, 111, {"ativo": False})
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}]},
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "fallback@empresa.com"


def test_evento_nao_suportado_e_ignorado_sem_chamar_clickup(conexao):
    item = {
        "id": "hist-3",
        "tipo_evento": "folderCreated",
        "task_id": None,
        "autor_id": 999,
        "before": None,
        "after": None,
    }

    with responses.RequestsMock():
        processar_evento(conexao, item, CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes == []


def mockar_tarefa_generica():
    """Tarefa minima, sem responsavel/solicitante - usada nos testes de
    atribuicao onde so a resolucao de before/after importa."""
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"id": "abc123", "assignees": [], "custom_fields": []},
        status=200,
    )


@responses.activate
def test_processa_atribuicao_tambem_busca_a_tarefa(conexao):
    """Revisado (Q2 do template de email): antes esse evento nao buscava a
    tarefa; agora busca, pra ter titulo/status/prioridade no email tambem
    nesse tipo de evento."""
    mapeamentos_repository.criar(conexao, 222, "ciclano@gmail.com", "ciclano@empresa.com", "Ciclano")
    mockar_tarefa_generica()
    item = {
        "id": "hist-2",
        "tipo_evento": "taskAssigneeUpdated",
        "task_id": "abc123",
        "autor_id": 999,
        "before": [],
        "after": [222],
    }

    processar_evento(conexao, item, CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes[0]["destinatario_email"] == "ciclano@empresa.com"
    assert len(responses.calls) == 1


@responses.activate
def test_processa_atribuicao_com_after_como_objeto_unico_nao_lista(conexao):
    """Formato real confirmado em producao: para 1 pessoa, o ClickUp manda
    um objeto, nao uma lista - iterar isso como lista quebra silenciosamente
    (itera as chaves do dict) se nao for tratado."""
    mockar_tarefa_generica()
    item = {
        "id": "hist-3",
        "tipo_evento": "taskAssigneeUpdated",
        "task_id": "abc123",
        "autor_id": 999,
        "before": None,
        "after": {
            "id": 222,
            "username": "Ciclano",
            "email": "ciclano@gmail.com",
        },
    }

    processar_evento(conexao, item, CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert len(notificacoes) == 1
    assert notificacoes[0]["destinatario_email"] == "ciclano@gmail.com"

    mapeamento = mapeamentos_repository.buscar_por_id(conexao, 222)
    assert mapeamento["nome"] == "Ciclano"


@responses.activate
def test_processa_autoatribuicao_com_after_como_objeto_unico_e_suprimida(conexao):
    """Mesmo cenario, mas quem se atribui e o proprio autor da acao - nao
    deve gerar nenhuma notificacao (regra de supressao por ator)."""
    mockar_tarefa_generica()
    item = {
        "id": "hist-4",
        "tipo_evento": "taskAssigneeUpdated",
        "task_id": "abc123",
        "autor_id": 222,
        "before": None,
        "after": {
            "id": 222,
            "username": "Ciclano",
            "email": "ciclano@gmail.com",
        },
    }

    processar_evento(conexao, item, CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes == []


@responses.activate
def test_autor_suprimido_ainda_e_auto_cadastrado(conexao):
    """Mesmo quando ninguem e notificado (autor e o unico responsavel,
    suprimido pela propria acao), quem apareceu no evento deve ser
    cadastrado - pra o time ir sendo conhecido aos poucos."""
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "assignees": [{"id": 111, "username": "Fulano", "email": "fulano@gmail.com"}],
            "custom_fields": [],
        },
        status=200,
    )
    item = {
        "id": "hist-5",
        "tipo_evento": "taskStatusUpdated",
        "task_id": "abc123",
        "autor_id": 111,
        "before": "a fazer",
        "after": "em desenvolvimento",
    }

    processar_evento(conexao, item, CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert notificacoes == []

    mapeamento = mapeamentos_repository.buscar_por_id(conexao, 111)
    assert mapeamento is not None
    assert mapeamento["nome"] == "Fulano"


@responses.activate
def test_usa_custom_id_no_conteudo_quando_disponivel(conexao):
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "custom_id": "DV-8165",
            "assignees": [],
            "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert "DV-8165" in notificacoes[0]["assunto"]
    assert "abc123" not in notificacoes[0]["assunto"]


@responses.activate
def test_sem_custom_id_usa_id_bruto_no_conteudo(conexao):
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "custom_id": None,
            "assignees": [],
            "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert "abc123" in notificacoes[0]["assunto"]


@responses.activate
def test_resolver_contexto_evento_retorna_metadados_da_tarefa(conexao):
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "id": "abc123",
            "custom_id": "DV-8165",
            "name": "Erro ao gerar boleto",
            "priority": {"priority": "high"},
            "text_content": "Descricao do problema",
            "status": {"status": "em desenvolvimento"},
            "assignees": [{"id": 111, "username": "Fulano", "email": "fulano@gmail.com"}],
            "custom_fields": [],
        },
        status=200,
    )

    _, _, metadados = resolver_contexto_evento(item_criacao(), CONFIG)

    assert metadados == {
        "identificador": "DV-8165",
        "titulo": "Erro ao gerar boleto",
        "prioridade": "Alta",
        "descricao": "Descricao do problema",
        "status_atual": "em desenvolvimento",
        "responsavel_nome": "Fulano",
        "solicitante_nome": "-",
    }


@responses.activate
def test_metadados_da_tarefa_tambem_disponivel_na_atribuicao(conexao):
    mockar_tarefa_generica()
    item = {
        "id": "hist-5",
        "tipo_evento": "taskAssigneeUpdated",
        "task_id": "abc123",
        "autor_id": 999,
        "before": [],
        "after": [222],
    }

    _, _, metadados = resolver_contexto_evento(item, CONFIG)

    assert metadados["identificador"] == "abc123"


@responses.activate
def test_dois_eventos_diferentes_do_clickup_para_mesma_criacao_nao_duplicam_email(conexao):
    """Reproduz bug real: o ClickUp as vezes manda 2 history_items com IDs
    diferentes ("taskCreated") pra uma unica criacao de chamado. Dedup por
    evento_id nao pega isso (IDs realmente diferentes) - precisa comparar
    o conteudo da notificacao."""
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={"assignees": [], "custom_fields": [{"name": "Solicitante", "value": {"id": 111}}]},
        status=200,
    )
    mapeamentos_repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")

    processar_evento(conexao, item_criacao(evento_id="hist-1"), CONFIG)
    processar_evento(conexao, item_criacao(evento_id="hist-2"), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    assert len(notificacoes) == 1


@responses.activate
def test_criacao_com_dois_solicitantes_notifica_e_cadastra_os_dois(conexao):
    """ADR-0012: antes so o primeiro solicitante da lista era considerado -
    o segundo era descartado silenciosamente, sem notificacao e sem
    auto-cadastro."""
    responses.add(
        responses.GET,
        "https://api.clickup.com/api/v2/task/abc123",
        json={
            "assignees": [],
            "custom_fields": [
                {
                    "name": "Solicitante",
                    "value": [
                        {"id": 111, "username": "Fulano", "email": "fulano@gmail.com"},
                        {"id": 222, "username": "Ciclano", "email": "ciclano@gmail.com"},
                    ],
                }
            ],
        },
        status=200,
    )

    processar_evento(conexao, item_criacao(), CONFIG)

    notificacoes = conexao.execute("SELECT * FROM notificacoes_enviadas").fetchall()
    destinatarios = {n["destinatario_email"] for n in notificacoes}
    assert destinatarios == {"fulano@gmail.com", "ciclano@gmail.com"}

    assert mapeamentos_repository.buscar_por_id(conexao, 111) is not None
    assert mapeamentos_repository.buscar_por_id(conexao, 222) is not None

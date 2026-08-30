import pytest

from clickup_notfy import db
from clickup_notfy.notificacoes import outbox_repository


@pytest.fixture
def conexao():
    conexao = db.conectar(":memory:")
    db.inicializar_schema(conexao)
    yield conexao
    conexao.close()


def criar_pendente(conexao, evento_id, destinatario_email, tipo_evento="taskCreated", task_id="abc123"):
    return outbox_repository.criar_pendente(
        conexao, evento_id, task_id, destinatario_email, tipo_evento, "Assunto", "Corpo"
    )


def test_criar_pendente_fica_com_status_pendente(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com")

    linha = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()

    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 0
    assert linha["assunto"] == "Assunto"
    assert linha["corpo"] == "Corpo"
    assert linha["task_id"] == "abc123"


def test_registrar_sucesso_marca_como_enviado(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com")

    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=True)

    linha = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    assert linha["status"] == "enviado"
    assert linha["tentativas"] == 1
    assert linha["enviado_em"] is not None


def test_registrar_falha_mantem_pendente_e_incrementa_tentativas(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com")

    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=False)

    linha = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 1
    assert linha["enviado_em"] is None


def test_listar_pendentes_ignora_enviados(conexao):
    id_pendente = criar_pendente(conexao, "hist-1", "a@empresa.com")
    id_enviado = criar_pendente(conexao, "hist-2", "b@empresa.com")
    outbox_repository.registrar_resultado_envio(conexao, id_enviado, sucesso=True)

    pendentes = outbox_repository.listar_pendentes(conexao)

    assert [p["id"] for p in pendentes] == [id_pendente]
    assert pendentes[0]["assunto"] == "Assunto"
    assert pendentes[0]["corpo"] == "Corpo"


def test_nao_enviada_recentemente_quando_nao_ha_nada(conexao):
    assert (
        outbox_repository.ja_enviada_recentemente(conexao, "abc123", "taskCreated", "a@empresa.com", "Corpo")
        is False
    )


def test_enviada_recentemente_com_mesmo_conteudo_e_detectada(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com", task_id="abc123")
    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=True)

    assert (
        outbox_repository.ja_enviada_recentemente(conexao, "abc123", "taskCreated", "a@empresa.com", "Corpo")
        is True
    )


def test_nao_detecta_se_ainda_estiver_pendente_falha(conexao):
    """So conta como duplicata se o envio anterior teve sucesso - uma
    tentativa que falhou nao deve bloquear a proxima."""
    criar_pendente(conexao, "hist-1", "a@empresa.com", task_id="abc123")

    assert (
        outbox_repository.ja_enviada_recentemente(conexao, "abc123", "taskCreated", "a@empresa.com", "Corpo")
        is False
    )


def test_nao_detecta_conteudo_diferente(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com", task_id="abc123")
    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=True)

    ja_enviada = outbox_repository.ja_enviada_recentemente(
        conexao, "abc123", "taskCreated", "a@empresa.com", "Corpo diferente"
    )

    assert ja_enviada is False


def test_nao_detecta_tarefa_diferente(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com", task_id="abc123")
    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=True)

    ja_enviada = outbox_repository.ja_enviada_recentemente(
        conexao, "outra-tarefa", "taskCreated", "a@empresa.com", "Corpo"
    )

    assert ja_enviada is False


def test_nao_detecta_fora_da_janela_de_tempo(conexao):
    notificacao_id = criar_pendente(conexao, "hist-1", "a@empresa.com", task_id="abc123")
    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=True)
    conexao.execute(
        "UPDATE notificacoes_enviadas SET created_at = datetime('now', '-10 minutes') WHERE id = ?",
        (notificacao_id,),
    )
    conexao.commit()

    ja_enviada = outbox_repository.ja_enviada_recentemente(
        conexao, "abc123", "taskCreated", "a@empresa.com", "Corpo", janela_minutos=5
    )

    assert ja_enviada is False

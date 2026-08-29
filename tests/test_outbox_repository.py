import pytest

from clickup_notfy import db
from clickup_notfy.notificacoes import outbox_repository


@pytest.fixture
def conexao():
    conexao = db.conectar(":memory:")
    db.inicializar_schema(conexao)
    yield conexao
    conexao.close()


def test_criar_pendente_fica_com_status_pendente(conexao):
    notificacao_id = outbox_repository.criar_pendente(conexao, "hist-1", "a@empresa.com", "taskCreated")

    linha = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()

    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 0


def test_registrar_sucesso_marca_como_enviado(conexao):
    notificacao_id = outbox_repository.criar_pendente(conexao, "hist-1", "a@empresa.com", "taskCreated")

    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=True)

    linha = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    assert linha["status"] == "enviado"
    assert linha["tentativas"] == 1
    assert linha["enviado_em"] is not None


def test_registrar_falha_mantem_pendente_e_incrementa_tentativas(conexao):
    notificacao_id = outbox_repository.criar_pendente(conexao, "hist-1", "a@empresa.com", "taskCreated")

    outbox_repository.registrar_resultado_envio(conexao, notificacao_id, sucesso=False)

    linha = conexao.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 1
    assert linha["enviado_em"] is None


def test_listar_pendentes_ignora_enviados(conexao):
    id_pendente = outbox_repository.criar_pendente(conexao, "hist-1", "a@empresa.com", "taskCreated")
    id_enviado = outbox_repository.criar_pendente(conexao, "hist-2", "b@empresa.com", "taskCreated")
    outbox_repository.registrar_resultado_envio(conexao, id_enviado, sucesso=True)

    pendentes = outbox_repository.listar_pendentes(conexao)

    assert [p["id"] for p in pendentes] == [id_pendente]

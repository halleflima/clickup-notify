import pytest

from clickup_notfy import db
from clickup_notfy.webhook.dedup import evento_ja_processado, registrar_evento


@pytest.fixture
def conexao():
    conexao = db.conectar(":memory:")
    db.inicializar_schema(conexao)
    yield conexao
    conexao.close()


def test_evento_novo_nao_esta_processado(conexao):
    assert evento_ja_processado(conexao, "hist-1") is False


def test_evento_registrado_passa_a_estar_processado(conexao):
    registrar_evento(conexao, "hist-1", "taskCreated", "abc123", "{}")

    assert evento_ja_processado(conexao, "hist-1") is True


def test_registrar_evento_duplicado_falha(conexao):
    registrar_evento(conexao, "hist-1", "taskCreated", "abc123", "{}")

    with pytest.raises(Exception):
        registrar_evento(conexao, "hist-1", "taskCreated", "abc123", "{}")

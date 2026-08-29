import pytest

from clickup_notfy import db
from clickup_notfy.mapeamentos import repository


@pytest.fixture
def conexao():
    conexao = db.conectar(":memory:")
    db.inicializar_schema(conexao)
    yield conexao
    conexao.close()


def test_criar_e_buscar_mapeamento(conexao):
    repository.criar(conexao, 111, "fulano@gmail.com", "fulano@empresa.com", "Fulano")

    mapeamento = repository.buscar_por_id(conexao, 111)

    assert mapeamento["clickup_user_id"] == 111
    assert mapeamento["official_email"] == "fulano@empresa.com"
    assert mapeamento["ativo"] is True


def test_buscar_inexistente_retorna_none(conexao):
    assert repository.buscar_por_id(conexao, 999) is None


def test_listar_filtra_por_ativos(conexao):
    repository.criar(conexao, 111, "a@gmail.com", "a@empresa.com", "A")
    repository.criar(conexao, 222, "b@gmail.com", "b@empresa.com", "B")
    repository.atualizar(conexao, 222, {"ativo": False})

    assert [m["clickup_user_id"] for m in repository.listar(conexao, apenas_ativos=True)] == [111]
    assert [m["clickup_user_id"] for m in repository.listar(conexao, apenas_ativos=False)] == [222]
    assert len(repository.listar(conexao)) == 2


def test_atualizar_ignora_campos_desconhecidos(conexao):
    repository.criar(conexao, 111, "a@gmail.com", "a@empresa.com", "A")

    atualizou = repository.atualizar(
        conexao, 111, {"clickup_user_id": 999, "nome": "Novo Nome"}
    )

    mapeamento = repository.buscar_por_id(conexao, 111)
    assert atualizou is True
    assert mapeamento["nome"] == "Novo Nome"
    assert repository.buscar_por_id(conexao, 999) is None

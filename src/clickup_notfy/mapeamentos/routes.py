from flask import Blueprint, current_app, jsonify, request

from clickup_notfy import db
from clickup_notfy.auth import exigir_bearer_token
from clickup_notfy.mapeamentos import repository

mapeamentos_bp = Blueprint("mapeamentos", __name__, url_prefix="/mapeamentos-email")

CAMPOS_OBRIGATORIOS = {"clickup_user_id", "clickup_email", "official_email", "nome"}


def _conexao():
    return db.conectar(current_app.config["DATABASE_PATH"])


_NOME_TIPO_EM_PORTUGUES = {list: "lista", str: "texto", int: "numero", float: "numero", bool: "booleano"}


def _corpo_json_como_dict() -> tuple[dict | None, str | None]:
    """Retorna (dados, None) se o corpo for um objeto JSON valido, ou
    (None, mensagem_de_erro) caso contrario - distinguindo JSON malformado
    (erro de sintaxe) de JSON valido mas do tipo errado (ex: uma lista)."""
    dados = request.get_json(silent=True)

    if dados is None:
        return None, "corpo ausente ou nao e um JSON valido (verifique a sintaxe, ex: virgula sobrando)"
    if not isinstance(dados, dict):
        nome_tipo = _NOME_TIPO_EM_PORTUGUES.get(type(dados), type(dados).__name__)
        return None, f"corpo precisa ser um objeto JSON ({{...}}), recebido: {nome_tipo}"

    return dados, None


@mapeamentos_bp.route("", methods=["POST"])
@exigir_bearer_token
def criar_mapeamento():
    dados, erro = _corpo_json_como_dict()
    if erro is not None:
        return jsonify({"erro": erro}), 400

    faltando = CAMPOS_OBRIGATORIOS - dados.keys()
    if faltando:
        return jsonify({"erro": f"campos obrigatorios faltando: {sorted(faltando)}"}), 400

    conexao = _conexao()
    try:
        if repository.buscar_por_id(conexao, dados["clickup_user_id"]):
            return jsonify({"erro": "mapeamento ja existe para esse clickup_user_id"}), 409

        repository.criar(
            conexao,
            dados["clickup_user_id"],
            dados["clickup_email"],
            dados["official_email"],
            dados["nome"],
        )
        return jsonify(repository.buscar_por_id(conexao, dados["clickup_user_id"])), 201
    finally:
        conexao.close()


@mapeamentos_bp.route("", methods=["GET"])
@exigir_bearer_token
def listar_mapeamentos():
    apenas_ativos = None
    if "ativo" in request.args:
        apenas_ativos = request.args["ativo"].lower() in {"1", "true", "sim"}

    conexao = _conexao()
    try:
        return jsonify(repository.listar(conexao, apenas_ativos))
    finally:
        conexao.close()


@mapeamentos_bp.route("/<int:clickup_user_id>", methods=["GET"])
@exigir_bearer_token
def obter_mapeamento(clickup_user_id):
    conexao = _conexao()
    try:
        mapeamento = repository.buscar_por_id(conexao, clickup_user_id)
        if not mapeamento:
            return jsonify({"erro": "mapeamento nao encontrado"}), 404
        return jsonify(mapeamento)
    finally:
        conexao.close()


@mapeamentos_bp.route("/<int:clickup_user_id>", methods=["PATCH"])
@exigir_bearer_token
def atualizar_mapeamento(clickup_user_id):
    dados, erro = _corpo_json_como_dict()
    if erro is not None:
        return jsonify({"erro": erro}), 400

    conexao = _conexao()
    try:
        if not repository.buscar_por_id(conexao, clickup_user_id):
            return jsonify({"erro": "mapeamento nao encontrado"}), 404

        repository.atualizar(conexao, clickup_user_id, dados)
        return jsonify(repository.buscar_por_id(conexao, clickup_user_id))
    finally:
        conexao.close()

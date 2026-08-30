from flask import Blueprint, current_app, jsonify, request

from clickup_notfy import db
from clickup_notfy.auth import exigir_bearer_token
from clickup_notfy.mapeamentos import repository

mapeamentos_bp = Blueprint("mapeamentos", __name__, url_prefix="/mapeamentos-email")

CAMPOS_OBRIGATORIOS = {"clickup_user_id", "clickup_email", "official_email", "nome"}


def _conexao():
    return db.conectar(current_app.config["DATABASE_PATH"])


def _corpo_json_como_dict() -> dict | None:
    """Retorna o corpo JSON da requisicao como dict, ou None se ausente,
    invalido, ou de outro tipo (ex: uma lista) - protege as rotas de POST
    e PATCH de tentarem tratar um array/string/numero como se fosse objeto."""
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else None


@mapeamentos_bp.route("", methods=["POST"])
@exigir_bearer_token
def criar_mapeamento():
    dados = _corpo_json_como_dict()
    if dados is None:
        return jsonify({"erro": "corpo da requisicao precisa ser um objeto JSON"}), 400

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
    dados = _corpo_json_como_dict()
    if dados is None:
        return jsonify({"erro": "corpo da requisicao precisa ser um objeto JSON"}), 400

    conexao = _conexao()
    try:
        if not repository.buscar_por_id(conexao, clickup_user_id):
            return jsonify({"erro": "mapeamento nao encontrado"}), 404

        repository.atualizar(conexao, clickup_user_id, dados)
        return jsonify(repository.buscar_por_id(conexao, clickup_user_id))
    finally:
        conexao.close()

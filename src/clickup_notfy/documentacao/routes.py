from flask import Blueprint, jsonify

from clickup_notfy.documentacao.rotas import DESCRICAO_ROTAS

documentacao_bp = Blueprint("documentacao", __name__)


@documentacao_bp.route("/", methods=["GET"])
def descrever_api():
    return jsonify(
        {
            "servico": "clickup-notfy",
            "descricao": "Traduz eventos do ClickUp em notificacoes por email no endereco corporativo oficial de cada colaborador.",
            "rotas": DESCRICAO_ROTAS,
        }
    )

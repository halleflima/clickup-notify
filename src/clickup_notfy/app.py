from flask import Flask

from clickup_notfy import db
from clickup_notfy.config import Config
from clickup_notfy.documentacao.routes import documentacao_bp
from clickup_notfy.mapeamentos.routes import mapeamentos_bp
from clickup_notfy.webhook.routes import webhook_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    conexao = db.conectar(app.config["DATABASE_PATH"])
    db.inicializar_schema(conexao)
    conexao.close()

    app.register_blueprint(webhook_bp)
    app.register_blueprint(mapeamentos_bp)
    app.register_blueprint(documentacao_bp)

    return app


if __name__ == "__main__":
    from clickup_notfy.scheduler import iniciar_scheduler

    app = create_app()
    iniciar_scheduler(app.config)
    app.run()

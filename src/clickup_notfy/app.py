from flask import Flask

from clickup_notfy import db
from clickup_notfy.config import Config
from clickup_notfy.webhook.routes import webhook_bp


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    conexao = db.conectar(app.config["DATABASE_PATH"])
    db.inicializar_schema(conexao)
    conexao.close()

    app.register_blueprint(webhook_bp)

    return app


if __name__ == "__main__":
    create_app().run()

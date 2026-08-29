import pytest

from clickup_notfy import db
from clickup_notfy.notificacoes import outbox_repository
from clickup_notfy.scheduler import iniciar_scheduler, purgar_notificacoes_antigas, retentar_pendentes

CONFIG = {
    "SMTP_HOST": "smtp.exemplo.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "usuario",
    "SMTP_PASSWORD": "senha",
    "EMAIL_REMETENTE": "notificacao@empresa.com",
}


@pytest.fixture
def conexao(tmp_path):
    caminho = str(tmp_path / "teste.db")
    conexao = db.conectar(caminho)
    db.inicializar_schema(conexao)
    conexao.close()
    return caminho


def test_retentar_pendentes_marca_como_enviado_quando_smtp_funciona(conexao, monkeypatch):
    monkeypatch.setattr(
        "clickup_notfy.scheduler.email_sender.tentar_enviar", lambda *a, **k: True
    )
    conexao_db = db.conectar(conexao)
    notificacao_id = outbox_repository.criar_pendente(
        conexao_db, "hist-1", "a@empresa.com", "taskCreated", "Assunto", "Corpo"
    )
    conexao_db.close()

    config = dict(CONFIG, DATABASE_PATH=conexao)
    retentar_pendentes(config)

    conexao_db = db.conectar(conexao)
    linha = conexao_db.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    conexao_db.close()
    assert linha["status"] == "enviado"


def test_retentar_pendentes_mantem_pendente_quando_smtp_falha(conexao, monkeypatch):
    monkeypatch.setattr(
        "clickup_notfy.scheduler.email_sender.tentar_enviar", lambda *a, **k: False
    )
    conexao_db = db.conectar(conexao)
    notificacao_id = outbox_repository.criar_pendente(
        conexao_db, "hist-1", "a@empresa.com", "taskCreated", "Assunto", "Corpo"
    )
    conexao_db.close()

    config = dict(CONFIG, DATABASE_PATH=conexao)
    retentar_pendentes(config)

    conexao_db = db.conectar(conexao)
    linha = conexao_db.execute(
        "SELECT * FROM notificacoes_enviadas WHERE id = ?", (notificacao_id,)
    ).fetchone()
    conexao_db.close()
    assert linha["status"] == "pendente"
    assert linha["tentativas"] == 1


def test_purgar_remove_notificacoes_com_mais_de_dois_anos(conexao):
    conexao_db = db.conectar(conexao)
    conexao_db.execute(
        """
        INSERT INTO notificacoes_enviadas
            (evento_id, destinatario_email, tipo_evento, assunto, corpo, created_at)
        VALUES ('hist-antigo', 'a@empresa.com', 'taskCreated', 'A', 'B', datetime('now', '-3 years'))
        """
    )
    conexao_db.execute(
        """
        INSERT INTO notificacoes_enviadas
            (evento_id, destinatario_email, tipo_evento, assunto, corpo, created_at)
        VALUES ('hist-recente', 'a@empresa.com', 'taskCreated', 'A', 'B', datetime('now'))
        """
    )
    conexao_db.commit()
    conexao_db.close()

    removidos = purgar_notificacoes_antigas({"DATABASE_PATH": conexao})

    assert removidos == 1
    conexao_db = db.conectar(conexao)
    restantes = conexao_db.execute("SELECT evento_id FROM notificacoes_enviadas").fetchall()
    conexao_db.close()
    assert [r["evento_id"] for r in restantes] == ["hist-recente"]


def test_iniciar_scheduler_registra_os_tres_jobs(conexao):
    scheduler = iniciar_scheduler(dict(CONFIG, DATABASE_PATH=conexao))
    try:
        ids = {job.id for job in scheduler.get_jobs()}
        assert ids == {"retry_pendentes", "purge_diario", "vacuum_mensal"}
    finally:
        scheduler.shutdown(wait=False)

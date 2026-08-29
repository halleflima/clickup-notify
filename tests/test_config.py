import importlib

from clickup_notfy import config as config_module


def test_smtp_port_vazio_usa_padrao(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "")

    modulo_recarregado = importlib.reload(config_module)

    assert modulo_recarregado.Config.SMTP_PORT == 587


def test_smtp_port_customizado_e_respeitado(monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "2525")

    modulo_recarregado = importlib.reload(config_module)

    assert modulo_recarregado.Config.SMTP_PORT == 2525

    importlib.reload(config_module)

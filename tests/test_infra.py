"""Configuração, comandos e casos de borda fora das regras de negócio."""
import pytest

from app import create_app
from app.comandos import init_db
from app.config import Desenvolvimento


def test_create_app_sem_chaves_secretas_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.setattr(Desenvolvimento, "SECRET_KEY", None)

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("desenvolvimento")


def test_comando_init_db(app):
    resultado = app.test_cli_runner().invoke(init_db)

    assert resultado.exit_code == 0
    assert "inicializado" in resultado.output


def test_me_de_usuario_removido_responde_404(client, db, token_de):
    usuario, cabecalho = token_de("aluno")
    db.session.delete(usuario)
    db.session.commit()

    resposta = client.get("/api/v1/usuarios/me", headers=cabecalho)

    assert resposta.status_code == 404
    assert resposta.get_json() == {"message": "Usuário não encontrado."}


@pytest.mark.parametrize("papel", ["admin", "professor", "aluno"])
def test_fabrica_de_token_faz_login_de_verdade(client, token_de, papel):
    usuario, cabecalho = token_de(papel)

    corpo = client.get("/api/v1/usuarios/me", headers=cabecalho).get_json()

    assert (corpo["id"], corpo["papel"]) == (usuario.id, papel)

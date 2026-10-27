from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token
from werkzeug.exceptions import Forbidden

from app.auth import papel_requerido
from app.models import Usuario

REGISTRO = {"nome": "Bia", "email": "Bia@ReservaLab.dev", "senha": "segredo1"}


def registrar(client, **extra):
    return client.post("/api/v1/auth/registro", json={**REGISTRO, **extra})


def login(client, email="bia@reservalab.dev", senha="segredo1"):
    return client.post("/api/v1/auth/login", json={"email": email, "senha": senha})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---- registro ----

def test_registro_valido_cria_aluno_sem_expor_hash(client):
    resposta = registrar(client)

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["email"] == "bia@reservalab.dev"  # salvo em minúsculas
    assert corpo["papel"] == "aluno"
    assert "senha_hash" not in corpo and "senha" not in corpo
    assert set(corpo) == {"id", "nome", "email", "papel", "criado_em"}


def test_r11_registro_ignora_papel_enviado(client):
    resposta = registrar(client, papel="admin")

    assert resposta.status_code == 201
    assert resposta.get_json()["papel"] == "aluno"
    assert Usuario.query.one().papel == "aluno"


def test_registro_email_repetido_responde_409(client):
    registrar(client)
    resposta = registrar(client, email="bia@reservalab.dev")

    assert resposta.status_code == 409
    assert resposta.get_json() == {"message": "E-mail já cadastrado."}


@pytest.mark.parametrize("campo, valor, mensagem", [
    ("senha", None, "Informe uma senha com no mínimo 6 caracteres."),
    ("senha", "12345", "Informe uma senha com no mínimo 6 caracteres."),
    ("email", "nao-e-email", "Informe um e-mail válido."),
    ("email", None, "Informe um e-mail válido."),
    ("nome", "   ", "Informe o nome."),
])
def test_registro_campo_invalido_responde_400_com_mensagem_do_campo(client, campo, valor, mensagem):
    corpo = dict(REGISTRO)
    if valor is None:
        del corpo[campo]
    else:
        corpo[campo] = valor

    resposta = client.post("/api/v1/auth/registro", json=corpo)

    assert resposta.status_code == 400
    assert resposta.get_json() == {"message": {campo: mensagem}}


def test_registro_sem_content_type_json_responde_415_em_portugues(client):
    resposta = client.post("/api/v1/auth/registro", data="nome=Bia&email=b@x.dev&senha=segredo1",
                           content_type="application/x-www-form-urlencoded")

    assert resposta.status_code == 415
    assert resposta.get_json() == {
        "message": "Envie o corpo da requisição como JSON (Content-Type: application/json)."
    }


def test_registro_com_json_malformado_responde_400_em_portugues(client):
    resposta = client.post("/api/v1/auth/registro", data="{ruim", content_type="application/json")

    assert resposta.status_code == 400
    assert resposta.get_json() == {"message": "Requisição inválida: verifique se o corpo é um JSON válido."}


# ---- login ----

def test_login_valido_devolve_token_com_papel(client, app):
    registrar(client)

    resposta = login(client, email="BIA@reservalab.dev")

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["token_type"] == "Bearer"
    assert corpo["expira_em_min"] == 60
    from flask_jwt_extended import decode_token
    assert decode_token(corpo["access_token"])["papel"] == "aluno"


@pytest.mark.parametrize("email, senha", [
    ("bia@reservalab.dev", "errada1"),
    ("ninguem@reservalab.dev", "segredo1"),
])
def test_login_invalido_responde_401_generico(client, email, senha):
    registrar(client)

    resposta = login(client, email=email, senha=senha)

    assert resposta.status_code == 401
    assert resposta.get_json() == {"message": "E-mail ou senha inválidos."}


# ---- /usuarios/me ----

def test_me_com_token_valido(client):
    registrar(client)
    token = login(client).get_json()["access_token"]

    resposta = client.get("/api/v1/usuarios/me", headers=auth(token))

    assert resposta.status_code == 200
    assert resposta.get_json()["email"] == "bia@reservalab.dev"


def test_me_sem_token_responde_401(client):
    resposta = client.get("/api/v1/usuarios/me")

    assert resposta.status_code == 401
    assert "ausente" in resposta.get_json()["message"]


def test_me_com_token_adulterado_responde_401(client):
    registrar(client)
    token = login(client).get_json()["access_token"]
    cabecalho, carga, assinatura = token.split(".")
    adulterado = f"{cabecalho}.{carga}.{assinatura[:-4]}AAAA"

    resposta = client.get("/api/v1/usuarios/me", headers=auth(adulterado))

    assert resposta.status_code == 401
    assert resposta.get_json() == {"message": "Token de acesso inválido."}


def test_me_com_token_expirado_responde_401(client, app):
    registrar(client)
    token = create_access_token(identity="1", expires_delta=timedelta(seconds=-1))

    resposta = client.get("/api/v1/usuarios/me", headers=auth(token))

    assert resposta.status_code == 401
    assert resposta.get_json() == {"message": "Token de acesso expirado. Faça login novamente."}


# ---- papel_requerido ----

@papel_requerido("admin")
def acao_de_admin():
    return "ok"


def test_papel_requerido_libera_papel_permitido(app):
    token = create_access_token(identity="1", additional_claims={"papel": "admin"})
    with app.test_request_context(headers=auth(token)):
        assert acao_de_admin() == "ok"


def test_papel_requerido_bloqueia_outros_papeis_com_403(app):
    token = create_access_token(identity="1", additional_claims={"papel": "aluno"})
    with app.test_request_context(headers=auth(token)):
        with pytest.raises(Forbidden) as erro:
            acao_de_admin()
    assert erro.value.data == {"message": "Acesso negado: esta ação exige o papel admin."}

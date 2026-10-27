"""Documentação interativa: a especificação cobre a API real e o fluxo do Swagger UI funciona."""
import re
from datetime import timedelta

from app.services import relogio
from conftest import SENHA_PADRAO

METODOS = {"get", "post", "put", "delete"}


def especificacao(client):
    return client.get("/apispec.json").get_json()


def test_swagger_ui_abre(client):
    resposta = client.get("/apidocs/")

    assert resposta.status_code == 200
    assert "/apispec.json" in resposta.get_data(as_text=True)


def test_especificacao_tem_tags_e_seguranca_bearer(client):
    spec = especificacao(client)

    assert spec["openapi"].startswith("3.")
    assert [t["name"] for t in spec["tags"]] == ["Saúde", "Autenticação", "Salas", "Reservas"]
    assert spec["components"]["securitySchemes"]["Bearer"] == {
        "type": "http", "scheme": "bearer", "bearerFormat": "JWT"}


def test_toda_rota_da_api_esta_documentada_e_vice_versa(app, client):
    spec = especificacao(client)
    prefixo = spec["servers"][0]["url"]
    documentadas = {(caminho, metodo) for caminho, ops in spec["paths"].items()
                    for metodo in ops if metodo in METODOS}

    reais = set()
    for regra in app.url_map.iter_rules():
        if regra.rule.startswith(prefixo):
            caminho = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", regra.rule[len(prefixo):])
            reais |= {(caminho, m.lower()) for m in regra.methods if m.lower() in METODOS}

    assert documentadas == reais


def test_toda_operacao_tem_tag_e_respostas_de_erro(client):
    for caminho, ops in especificacao(client)["paths"].items():
        for metodo, op in ops.items():
            if metodo not in METODOS:
                continue
            assert op["tags"], (caminho, metodo)
            codigos = set(op["responses"])
            if caminho != "/health":
                assert any(c.startswith(("4", "5")) for c in codigos), (caminho, metodo)
            if op.get("security"):
                assert "401" in codigos, (caminho, metodo)


def test_fluxo_login_authorize_post_reservas(client, criar_usuario, catalogo):
    """Faz as chamadas como o Swagger UI faria: URL = servers[0] + caminho e,
    depois do Authorize, o cabeçalho "Authorization: Bearer <token>"."""
    spec = especificacao(client)
    base = spec["servers"][0]["url"]
    assert "/auth/login" in spec["paths"] and "post" in spec["paths"]["/reservas"]
    aluno = criar_usuario("aluno")

    login = client.post(f"{base}/auth/login", json={"email": aluno.email, "senha": SENHA_PADRAO})
    token = login.get_json()["access_token"]

    dia = (relogio.agora() + timedelta(days=1)).date()
    resposta = client.post(
        f"{base}/reservas",
        json={"sala_id": catalogo["SALA-A101"].id, "inicio": f"{dia}T14:00:00",
              "fim": f"{dia}T15:00:00", "participantes": 6, "finalidade": "Reunião de orientação"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["finalidade"] == "Reunião de orientação"

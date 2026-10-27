import pytest
from flask import request
from flask_restful import abort

from app.resources.health import HealthResource


def test_rota_inexistente_responde_404_em_json(client):
    resposta = client.get("/api/v1/nao-existe")

    assert resposta.status_code == 404
    assert resposta.get_json() == {"message": "Recurso não encontrado."}


def test_metodo_nao_permitido_responde_405_em_json(client):
    resposta = client.post("/api/v1/health")

    assert resposta.status_code == 405
    assert resposta.get_json() == {"message": "Método não permitido."}


def test_corpo_que_nao_e_json_responde_415(client, monkeypatch):
    monkeypatch.setattr(HealthResource, "get", lambda self: request.json)

    resposta = client.get("/api/v1/health", data="texto", content_type="text/plain")

    assert resposta.status_code == 415
    assert resposta.get_json() == {
        "message": "Envie o corpo da requisição como JSON (Content-Type: application/json)."
    }


# PROPAGATE_EXCEPTIONS está ligado (por causa do JWT): o 500 em JSON
# precisa funcionar mesmo assim.
def test_erro_inesperado_em_resource_responde_500_em_json(app, client, monkeypatch):
    def explode(self):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(HealthResource, "get", explode)

    resposta = client.get("/api/v1/health")

    assert app.config["PROPAGATE_EXCEPTIONS"] is True
    assert resposta.status_code == 500
    assert resposta.get_json() == {"message": "Erro interno do servidor."}


def test_erro_inesperado_fora_da_api_responde_500_em_json(app, client):
    @app.get("/explode")
    def explode():
        raise RuntimeError("falha simulada")

    resposta = client.get("/explode")

    assert resposta.status_code == 500
    assert resposta.get_json() == {"message": "Erro interno do servidor."}


@pytest.mark.parametrize("codigo", [404, 405])
def test_mensagem_do_abort_tem_prioridade(client, monkeypatch, codigo):
    monkeypatch.setattr(HealthResource, "get", lambda self: abort(codigo, message="Sala não encontrada."))

    resposta = client.get("/api/v1/health")

    assert resposta.status_code == codigo
    assert resposta.get_json() == {"message": "Sala não encontrada."}

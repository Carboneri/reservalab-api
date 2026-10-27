def test_health_responde_ok(client):
    resposta = client.get("/api/v1/health")

    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok", "versao": "1.0.0"}

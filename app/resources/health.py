from flask_restful import Resource


# Um Resource representa um recurso da API; cada verbo HTTP vira um método.
class HealthResource(Resource):
    # GET /api/v1/health: o Flask-RESTful chama este método e serializa
    # o dict retornado como JSON, com status 200 por padrão.
    def get(self):
        return {"status": "ok", "versao": "1.0.0"}

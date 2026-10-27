from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restful import Resource, abort, marshal_with

from app.campos import usuario_campos
from app.services import usuarios


class UsuarioMeResource(Resource):
    # jwt_required: sem token válido, o Flask-JWT-Extended responde 401.
    @jwt_required()
    @marshal_with(usuario_campos)
    def get(self):
        usuario = usuarios.buscar_por_id(int(get_jwt_identity()))
        if usuario is None:
            abort(404, message="Usuário não encontrado.")
        return usuario

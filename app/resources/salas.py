from flask import url_for
from flask_restful import Resource, abort, marshal_with

from app.auth import papel_requerido
from app.campos import disponibilidade_campos, paginado, sala_campos
from app.parsers import disponibilidade_parser, sala_parser, salas_filtro_parser
from app.services import disponibilidade, salas
from app.services.excecoes import CodigoSalaJaCadastrado, SalaComReservasFuturas


def obter_sala_ou_404(sala_id):
    sala = salas.obter(sala_id)
    if sala is None:
        abort(404, message=f"Sala {sala_id} não encontrada.")
    return sala


# Padrão do Flask-RESTful: um Resource para a coleção (/salas) ...
class SalaListResource(Resource):
    @marshal_with(paginado(sala_campos))
    def get(self):
        filtros = salas_filtro_parser.parse_args()
        return salas.listar(**filtros)

    @papel_requerido("admin")
    @marshal_with(sala_campos)
    def post(self):
        dados = sala_parser.parse_args()
        try:
            sala = salas.criar(dados)
        except CodigoSalaJaCadastrado:
            abort(409, message=f"Já existe uma sala com o código {dados['codigo']}.")
        # 201 Created + Location: onde o novo recurso pode ser consultado.
        return sala, 201, {"Location": url_for("sala", sala_id=sala.id)}


# ... e outro para um item da coleção (/salas/<id>).
class SalaResource(Resource):
    @marshal_with(sala_campos)
    def get(self, sala_id):
        return obter_sala_ou_404(sala_id)

    @papel_requerido("admin")
    @marshal_with(sala_campos)
    def put(self, sala_id):
        sala = obter_sala_ou_404(sala_id)
        dados = sala_parser.parse_args()
        try:
            return salas.substituir(sala, dados)
        except CodigoSalaJaCadastrado:
            abort(409, message=f"Já existe uma sala com o código {dados['codigo']}.")

    @papel_requerido("admin")
    def delete(self, sala_id):
        sala = obter_sala_ou_404(sala_id)
        try:
            salas.excluir(sala)
        except SalaComReservasFuturas:
            abort(409, message="A sala tem reservas confirmadas que ainda não terminaram; "
                               "cancele-as antes de excluir.")
        return "", 204  # 204 No Content: sucesso, sem corpo


class SalaDisponibilidadeResource(Resource):
    @marshal_with(disponibilidade_campos)
    def get(self, sala_id):
        sala = obter_sala_ou_404(sala_id)
        dia = disponibilidade_parser.parse_args()["data"]
        return disponibilidade.da_sala(sala, dia)

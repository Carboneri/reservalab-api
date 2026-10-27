from functools import wraps

from flask import url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from flask_restful import Resource, abort, marshal, marshal_with

from app.campos import conflito_campos, paginado, reserva_campos
from app.parsers import reserva_parser, reservas_filtro_parser
from app.services import reservas
from app.services.excecoes import ConflitoReserva, RegraViolada


def traduzir_erros(metodo):
    """Único ponto em que exceções de negócio viram respostas HTTP."""

    @wraps(metodo)
    def wrapper(*args, **kwargs):
        try:
            return metodo(*args, **kwargs)
        except RegraViolada as erro:
            abort(erro.status, message=erro.mensagem)
        except ConflitoReserva as erro:
            abort(409, message="A sala já está reservada nesse horário.",
                  conflito=marshal(erro.reserva_existente, conflito_campos))

    return wrapper


def usuario_logado():
    """(id, papel) de quem fez a requisição, lidos do token JWT."""
    return int(get_jwt_identity()), get_jwt()["papel"]


class ReservaListResource(Resource):
    # method_decorators vale para todos os métodos; o primeiro da lista fica por dentro.
    method_decorators = [traduzir_erros, jwt_required()]

    @marshal_with(paginado(reserva_campos))
    def get(self):
        filtros = reservas_filtro_parser.parse_args()
        return reservas.listar(*usuario_logado(), **filtros)

    @marshal_with(reserva_campos)
    def post(self):
        dados = reserva_parser.parse_args()
        reserva = reservas.criar(*usuario_logado(), **dados)
        return reserva, 201, {"Location": url_for("reserva", reserva_id=reserva.id)}


class ReservaResource(Resource):
    method_decorators = [traduzir_erros, jwt_required()]

    # Reserva de outra pessoa responde 404, não 403: um 403 confirmaria
    # que aquele id existe. A regra está em reservas.obter().
    @marshal_with(reserva_campos)
    def get(self, reserva_id):
        return reservas.obter(reserva_id, *usuario_logado())

    def delete(self, reserva_id):
        reservas.cancelar(reserva_id, *usuario_logado())
        return "", 204  # cancelada (R9): o registro continua, só muda o status

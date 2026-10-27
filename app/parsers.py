import re
from datetime import datetime

from flask_restful import inputs, reqparse

from app.models.reserva import STATUS_RESERVA
from app.models.sala import TIPOS_SALA

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAIOR_INTEIRO = 2**63 - 1  # maior INTEGER que o SQLite consegue guardar


class ArgumentoNaoNulo(reqparse.Argument):
    """Por padrão o reqparse aceita null e entrega None ao código (que quebraria
    com 500 adiante). Com nullable=False, null vira 400 com a mensagem do campo."""

    def __init__(self, *args, nullable=False, **kwargs):
        super().__init__(*args, nullable=nullable, **kwargs)


# Tipos do reqparse: recebem o valor bruto e devolvem o convertido,
# ou levantam ValueError (que vira 400 com a mensagem do campo).
def texto_obrigatorio(valor):
    valor = str(valor).strip()
    if not valor:
        raise ValueError("vazio")
    return valor


def email(valor):
    valor = str(valor).strip().lower()
    if not EMAIL_REGEX.match(valor):
        raise ValueError("e-mail inválido")
    return valor


def codigo_sala(valor):
    return texto_obrigatorio(valor).upper()


def item_de_recurso(valor):
    # Recursos são guardados como "projetor,som": uma vírgula no item o partiria em dois.
    valor = texto_obrigatorio(valor)
    if "," in valor:
        raise ValueError("vírgula")
    return valor


def inteiro_positivo(valor):
    """inputs.positive, mais rígido: recusa true/false e decimais (que ele
    converteria para 1/0 e truncaria) e números acima do limite do banco."""
    if isinstance(valor, bool) or (isinstance(valor, float) and not valor.is_integer()):
        raise ValueError("não é inteiro")
    numero = inputs.positive(valor)
    if numero > MAIOR_INTEIRO:
        raise ValueError("grande demais")
    return numero


def data_iso(valor):
    return inputs.date(valor).date()  # "2026-11-10" → date(2026, 11, 10)


def data_hora_iso(valor):
    """"2026-11-10T14:00:00" → datetime. Sem fuso: horário local do campus (SPEC 2.4)."""
    data_hora = datetime.fromisoformat(str(valor))
    if data_hora.tzinfo is not None:
        raise ValueError("com fuso")
    return data_hora


def texto_curto(valor):
    valor = texto_obrigatorio(valor)
    if len(valor) > 120:
        raise ValueError("longo demais")
    return valor


def senha(valor):
    valor = str(valor)
    if len(valor) < 6:
        raise ValueError("senha curta")
    return valor


# location="json": só lê o corpo JSON. "help" é a mensagem devolvida
# no 400, tanto para campo ausente quanto para valor inválido.
registro_parser = reqparse.RequestParser(argument_class=ArgumentoNaoNulo)
registro_parser.add_argument("nome", type=texto_obrigatorio, required=True,
                             location="json", help="Informe o nome.")
registro_parser.add_argument("email", type=email, required=True,
                             location="json", help="Informe um e-mail válido.")
registro_parser.add_argument("senha", type=senha, required=True,
                             location="json", help="Informe uma senha com no mínimo 6 caracteres.")

login_parser = reqparse.RequestParser(argument_class=ArgumentoNaoNulo)
login_parser.add_argument("email", type=email, required=True,
                          location="json", help="Informe um e-mail válido.")
login_parser.add_argument("senha", type=str, required=True,
                          location="json", help="Informe a senha.")


# ---- Salas ----

sala_parser = reqparse.RequestParser(argument_class=ArgumentoNaoNulo)
sala_parser.add_argument("codigo", type=codigo_sala, required=True,
                         location="json", help="Informe o código da sala (ex.: LAB-B204).")
sala_parser.add_argument("nome", type=texto_obrigatorio, required=True,
                         location="json", help="Informe o nome da sala.")
sala_parser.add_argument("bloco", type=texto_obrigatorio, required=True,
                         location="json", help="Informe o bloco.")
# choices: o reqparse recusa (400) qualquer valor fora da lista.
sala_parser.add_argument("tipo", choices=TIPOS_SALA, required=True,
                         location="json", help=f"Tipo deve ser um de: {', '.join(TIPOS_SALA)}.")
# inteiro_positivo: inteiro maior que zero (usa o inputs.positive do Flask-RESTful).
sala_parser.add_argument("capacidade", type=inteiro_positivo, required=True,
                         location="json", help="Capacidade deve ser um inteiro maior que zero.")
# action="append" com JSON: o cliente envia uma lista (["projetor", "som"]) e
# recebe uma lista na resposta. Mais simples de explicar do que texto com vírgulas.
sala_parser.add_argument("recursos", type=item_de_recurso, action="append", default=[],
                         location="json", help="Recursos devem ser uma lista de textos sem vírgula.")
sala_parser.add_argument("ativa", type=inputs.boolean, default=True,
                         location="json", help="Ativa deve ser true ou false.")

# Paginação reaproveitável: outros parsers de listagem partem de uma cópia dele.
paginacao_parser = reqparse.RequestParser(argument_class=ArgumentoNaoNulo)
paginacao_parser.add_argument("page", type=inteiro_positivo, default=1, location="args",
                              help="page deve ser um inteiro maior ou igual a 1.")
paginacao_parser.add_argument("per_page", type=inteiro_positivo, default=10, location="args",
                              help="per_page deve ser um inteiro maior ou igual a 1.")

salas_filtro_parser = paginacao_parser.copy()
salas_filtro_parser.add_argument("tipo", choices=TIPOS_SALA, location="args",
                                 help=f"tipo deve ser um de: {', '.join(TIPOS_SALA)}.")
salas_filtro_parser.add_argument("bloco", type=texto_obrigatorio, location="args",
                                 help="bloco não pode ser vazio.")
salas_filtro_parser.add_argument("capacidade_min", type=inteiro_positivo, location="args",
                                 help="capacidade_min deve ser um inteiro maior que zero.")
salas_filtro_parser.add_argument("recurso", type=texto_obrigatorio, location="args",
                                 help="recurso não pode ser vazio.")
salas_filtro_parser.add_argument("ativa", type=inputs.boolean, location="args",
                                 help="ativa deve ser true ou false.")

disponibilidade_parser = reqparse.RequestParser(argument_class=ArgumentoNaoNulo)
disponibilidade_parser.add_argument("data", type=data_iso, required=True,
                                    location="args", help="Informe a data no formato AAAA-MM-DD.")


# ---- Reservas ----
# Aqui só o formato. As regras (duração, horário, conflito...) ficam no serviço.

reserva_parser = reqparse.RequestParser(argument_class=ArgumentoNaoNulo)
reserva_parser.add_argument("sala_id", type=inteiro_positivo, required=True,
                            location="json", help="Informe o id da sala (inteiro maior que zero).")
reserva_parser.add_argument("inicio", type=data_hora_iso, required=True, location="json",
                            help="Informe o início no formato AAAA-MM-DDTHH:MM:SS, sem fuso.")
reserva_parser.add_argument("fim", type=data_hora_iso, required=True, location="json",
                            help="Informe o fim no formato AAAA-MM-DDTHH:MM:SS, sem fuso.")
reserva_parser.add_argument("participantes", type=inteiro_positivo, required=True,
                            location="json", help="Participantes deve ser um inteiro maior que zero.")
reserva_parser.add_argument("finalidade", type=texto_curto, required=True,
                            location="json", help="Informe a finalidade (até 120 caracteres).")

reservas_filtro_parser = paginacao_parser.copy()
reservas_filtro_parser.add_argument("sala_id", type=inteiro_positivo, location="args",
                                    help="sala_id deve ser um inteiro maior que zero.")
reservas_filtro_parser.add_argument("data", type=data_iso, location="args",
                                    help="data deve estar no formato AAAA-MM-DD.")
reservas_filtro_parser.add_argument("status", choices=STATUS_RESERVA, location="args",
                                    help=f"status deve ser um de: {', '.join(STATUS_RESERVA)}.")

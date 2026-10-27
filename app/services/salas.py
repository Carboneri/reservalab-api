from sqlalchemy import func

from app.extensions import db
from app.models import Reserva, Sala
from app.services import relogio
from app.services.excecoes import CodigoSalaJaCadastrado, SalaComReservasFuturas

POR_PAGINA_MAX = 50
CAMPOS_EDITAVEIS = ("codigo", "nome", "bloco", "tipo", "capacidade", "recursos", "ativa")


def obter(sala_id):
    return db.session.get(Sala, sala_id)


def listar(page, per_page, tipo=None, bloco=None, capacidade_min=None, recurso=None, ativa=None):
    consulta = Sala.query.order_by(Sala.codigo)
    if tipo:
        consulta = consulta.filter(Sala.tipo == tipo)
    if bloco:
        consulta = consulta.filter(func.lower(Sala.bloco) == bloco.lower())
    if capacidade_min:
        consulta = consulta.filter(Sala.capacidade >= capacidade_min)
    if recurso:
        # Recursos ficam como "projetor,som": cercar com vírgulas faz o LIKE
        # achar o item inteiro ("som" não casa com "sonorizacao").
        texto = func.lower("," + Sala.recursos_texto + ",")
        # Escapa % e _ para o LIKE tratá-los como texto, não como curinga.
        termo = recurso.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        consulta = consulta.filter(texto.like(f"%,{termo},%", escape="\\"))
    if ativa is not None:
        consulta = consulta.filter(Sala.ativa == ativa)

    # per_page acima do máximo é reduzido em silêncio (SPEC 4.1).
    return consulta.paginate(page=page, per_page=min(per_page, POR_PAGINA_MAX), error_out=False)


def _garantir_codigo_livre(codigo, sala_id=None):
    existente = Sala.query.filter_by(codigo=codigo).first()
    if existente and existente.id != sala_id:
        raise CodigoSalaJaCadastrado()


def criar(dados):
    _garantir_codigo_livre(dados["codigo"])
    sala = Sala(**{campo: dados[campo] for campo in CAMPOS_EDITAVEIS})
    db.session.add(sala)
    db.session.commit()
    return sala


def substituir(sala, dados):
    """PUT: todos os campos editáveis são trocados pelos novos valores."""
    _garantir_codigo_livre(dados["codigo"], sala.id)
    for campo in CAMPOS_EDITAVEIS:
        setattr(sala, campo, dados[campo])
    db.session.commit()
    return sala


def excluir(sala):
    """R10: bloqueia se houver reserva confirmada que ainda não terminou."""
    pendente = Reserva.query.filter(
        Reserva.sala_id == sala.id,
        Reserva.status == "confirmada",
        Reserva.fim > relogio.agora(),
    ).first()
    if pendente:
        raise SalaComReservasFuturas()

    db.session.delete(sala)  # o cascade apaga as reservas passadas e canceladas
    db.session.commit()

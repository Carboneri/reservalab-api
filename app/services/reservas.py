"""Regras de negócio das reservas (R1 a R9). Nada de Flask ou HTTP aqui.

Ordem de validação ao criar uma reserva (a primeira regra violada decide a resposta):

    1. Formato dos campos ............ 400  (reqparse, antes de chegar aqui)
    2. R1 duração, R2 passado, R3 horário de funcionamento ... 400
    3. Sala existe ................... 404
    4. R6 sala inativa ............... 422
    5. R7 auditório só professor/admin 403
    6. R5 capacidade ................. 422
    7. R8 limite de reservas do aluno  422
    8. R4 conflito de horário ........ 409

Primeiro o que depende só dos dados enviados, depois o que exige consultar o banco,
e por último o conflito, a consulta mais cara.
"""
from datetime import datetime, time, timedelta

from app.extensions import db
from app.models import Reserva
from app.services import relogio, salas
from app.services.disponibilidade import ABERTURA, FECHAMENTO
from app.services.excecoes import ConflitoReserva, RegraViolada
from app.services.salas import POR_PAGINA_MAX

DURACAO_MINIMA = timedelta(minutes=30)
DURACAO_MAXIMA = timedelta(hours=4)
LIMITE_RESERVAS_ALUNO = 3


def _validar_horario(inicio, fim):
    # R1: fim depois do início, entre 30 min e 4 h.
    if fim <= inicio:
        raise RegraViolada(400, "O fim da reserva deve ser depois do início.")
    if not DURACAO_MINIMA <= fim - inicio <= DURACAO_MAXIMA:
        raise RegraViolada(400, "A reserva deve durar no mínimo 30 minutos e no máximo 4 horas.")
    # R2: nada de reservar no passado.
    if inicio < relogio.agora():
        raise RegraViolada(400, "Não é possível reservar no passado.")
    # R3: dentro do funcionamento (07:30–22:30), no mesmo dia.
    if inicio.date() != fim.date() or inicio.time() < ABERTURA or fim.time() > FECHAMENTO:
        raise RegraViolada(400, "Reservas só entre 07:30 e 22:30, com início e fim no mesmo dia.")


def _reservas_futuras_do_usuario(usuario_id):
    return Reserva.query.filter(
        Reserva.usuario_id == usuario_id,
        Reserva.status == "confirmada",
        Reserva.inicio > relogio.agora(),
    ).count()


def sobrepoe(inicio_a, fim_a, inicio_b, fim_b):
    """R4 numa linha (função pura): dois intervalos se sobrepõem quando cada um
    começa antes de o outro terminar. Com "<" estrito, 08:00–10:00 e 10:00–12:00
    não conflitam."""
    return inicio_a < fim_b and inicio_b < fim_a


def _conflito(sala_id, inicio, fim):
    # Pela R3 toda reserva cabe num único dia: basta olhar as confirmadas da sala
    # naquele dia e aplicar sobrepoe() em Python.
    inicio_do_dia = datetime.combine(inicio.date(), time.min)
    candidatas = Reserva.query.filter(
        Reserva.sala_id == sala_id,
        Reserva.status == "confirmada",
        Reserva.inicio >= inicio_do_dia,
        Reserva.inicio < inicio_do_dia + timedelta(days=1),
    ).order_by(Reserva.inicio)
    return next((r for r in candidatas if sobrepoe(inicio, fim, r.inicio, r.fim)), None)


def criar(usuario_id, papel, sala_id, inicio, fim, participantes, finalidade):
    """Cria uma reserva confirmada ou levanta RegraViolada/ConflitoReserva."""
    _validar_horario(inicio, fim)

    sala = salas.obter(sala_id)
    if sala is None:
        raise RegraViolada(404, f"Sala {sala_id} não encontrada.")
    if not sala.ativa:  # R6
        raise RegraViolada(422, f"A sala {sala.codigo} está inativa e não pode ser reservada.")
    if sala.tipo == "auditorio" and papel not in ("professor", "admin"):  # R7
        raise RegraViolada(403, "Auditórios só podem ser reservados por professores ou administradores.")
    if participantes > sala.capacidade:  # R5
        raise RegraViolada(422, f"A sala {sala.codigo} comporta {sala.capacidade} pessoas; "
                                f"foram informados {participantes} participantes.")
    if papel == "aluno" and _reservas_futuras_do_usuario(usuario_id) >= LIMITE_RESERVAS_ALUNO:  # R8
        raise RegraViolada(422, f"Alunos podem ter no máximo {LIMITE_RESERVAS_ALUNO} "
                                "reservas futuras confirmadas.")

    # A checagem de conflito e a inserção acontecem na mesma transação. Mesmo assim,
    # no SQLite duas requisições simultâneas podem ler "sem conflito" antes de gravar.
    # Em produção: constraint de exclusão no PostgreSQL (EXCLUDE USING gist com &&)
    # ou lock da sala (SELECT ... FOR UPDATE) antes da checagem.
    existente = _conflito(sala.id, inicio, fim)
    if existente:
        raise ConflitoReserva(existente)

    reserva = Reserva(sala=sala, usuario_id=usuario_id, inicio=inicio, fim=fim,
                      participantes=participantes, finalidade=finalidade)
    db.session.add(reserva)
    db.session.commit()
    return reserva


def listar(usuario_id, papel, page, per_page, sala_id=None, data=None, status=None):
    consulta = Reserva.query.order_by(Reserva.inicio, Reserva.id)
    if papel != "admin":  # aluno e professor só veem as próprias reservas
        consulta = consulta.filter(Reserva.usuario_id == usuario_id)
    if sala_id:
        consulta = consulta.filter(Reserva.sala_id == sala_id)
    if data:
        inicio_do_dia = datetime.combine(data, time.min)
        consulta = consulta.filter(Reserva.inicio >= inicio_do_dia,
                                   Reserva.inicio < inicio_do_dia + timedelta(days=1))
    if status:
        consulta = consulta.filter(Reserva.status == status)
    return consulta.paginate(page=page, per_page=min(per_page, POR_PAGINA_MAX), error_out=False)


def obter(reserva_id, usuario_id, papel):
    """Reserva visível para o usuário: a dele, ou qualquer uma se for admin."""
    reserva = db.session.get(Reserva, reserva_id)
    # Reserva de outra pessoa recebe a mesma resposta de uma inexistente:
    # assim não dá para descobrir quais ids existem testando um por um.
    if reserva is None or (papel != "admin" and reserva.usuario_id != usuario_id):
        raise RegraViolada(404, f"Reserva {reserva_id} não encontrada.")
    return reserva


def cancelar(reserva_id, usuario_id, papel):
    """R9: só o dono ou o admin; muda o status, não apaga."""
    reserva = obter(reserva_id, usuario_id, papel)
    if reserva.status == "cancelada":
        raise RegraViolada(409, "A reserva já está cancelada.")
    if reserva.inicio <= relogio.agora():
        raise RegraViolada(409, "A reserva já começou e não pode mais ser cancelada.")
    reserva.status = "cancelada"
    db.session.commit()
    return reserva

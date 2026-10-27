from datetime import datetime, time, timedelta

import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import Reserva, Sala, Usuario
from app.services import relogio, reservas
from app.services.excecoes import ErroDeNegocio

USUARIOS = [
    # (nome, email, senha, papel) — senhas simples de demonstração, listadas no README.
    ("Ana Admin", "admin@reservalab.dev", "admin123", "admin"),
    ("Paulo Professor", "professor@reservalab.dev", "prof123", "professor"),
    ("Alice Aluna", "aluno@reservalab.dev", "aluno123", "aluno"),
]

SALAS = [
    # (codigo, nome, bloco, tipo, capacidade, recursos, ativa)
    ("LAB-B204", "Laboratório de Programação", "B", "laboratorio", 40,
     ["computadores", "projetor", "ar-condicionado"], True),
    ("LAB-B206", "Laboratório de Redes", "B", "laboratorio", 30,
     ["computadores", "projetor"], True),
    ("LAB-C101", "Laboratório de Hardware", "C", "laboratorio", 25,
     ["bancadas", "projetor"], True),
    ("SALA-A101", "Sala de Aula A101", "A", "sala_aula", 45,
     ["projetor", "quadro-branco"], True),
    ("SALA-A102", "Sala de Aula A102", "A", "sala_aula", 45,
     ["quadro-branco", "ar-condicionado"], True),
    ("SALA-B110", "Sala de Estudos B110", "B", "sala_aula", 15,
     ["quadro-branco"], True),
    ("SALA-C203", "Sala de Aula C203 (em reforma)", "C", "sala_aula", 35,
     ["projetor"], False),
    ("AUD-A001", "Auditório Central", "A", "auditorio", 200,
     ["projetor", "som", "ar-condicionado"], True),
]

RESERVAS = [
    # (n-ésimo dia útil a partir de amanhã, sala, email, início, fim, participantes, finalidade)
    (1, "LAB-B204", "professor@reservalab.dev", "08:00", "10:00", 35, "Aula de Programação Web"),
    # Começa quando a anterior termina: horários encostados não conflitam (R4).
    (1, "LAB-B204", "aluno@reservalab.dev", "10:00", "12:00", 4, "Estudo em grupo"),
    (2, "AUD-A001", "admin@reservalab.dev", "19:00", "22:30", 150, "Palestra de abertura da semana acadêmica"),
    (3, "SALA-A101", "aluno@reservalab.dev", "14:00", "15:30", 6, "Reunião do projeto integrador"),
    (4, "LAB-B206", "professor@reservalab.dev", "07:30", "09:30", 28, "Aula de Redes de Computadores"),
    (5, "LAB-C101", "professor@reservalab.dev", "13:00", "17:00", 20, "Oficina de Arduino"),
]


def proximo_dia_util(n, hoje=None):
    """Devolve o n-ésimo dia útil depois de hoje (sábado e domingo não contam)."""
    dia = hoje or relogio.agora().date()
    while n > 0:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            n -= 1
    return dia


@click.command("init-db")
@with_appcontext
def init_db():
    """Cria as tabelas que ainda não existem."""
    db.create_all()
    click.echo("Banco de dados inicializado.")


@click.command("seed")
@with_appcontext
def seed():
    """Insere dados de exemplo; rodar de novo não duplica nada."""
    db.create_all()

    # Idempotência: cada item é buscado pela chave única antes de ser criado.
    usuarios = {}
    for nome, email, senha, papel in USUARIOS:
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario is None:
            usuario = Usuario(nome=nome, email=email, papel=papel)
            usuario.definir_senha(senha)
            db.session.add(usuario)
        usuarios[email] = usuario

    salas = {}
    for codigo, nome, bloco, tipo, capacidade, recursos, ativa in SALAS:
        sala = Sala.query.filter_by(codigo=codigo).first()
        if sala is None:
            sala = Sala(codigo=codigo, nome=nome, bloco=bloco, tipo=tipo,
                        capacidade=capacidade, recursos=recursos, ativa=ativa)
            db.session.add(sala)
        salas[codigo] = sala
    db.session.commit()

    # Reservas só num banco ainda sem reservas: as datas são relativas a hoje, e
    # rodar o seed em outro dia criaria um segundo conjunto (o aluno chegaria ao
    # limite da R8 e a demo mudaria). Passam pelo serviço da API: obedecem R1–R8.
    criadas = 0
    if Reserva.query.first() is None:
        for n, codigo, email, ini, fim, participantes, finalidade in RESERVAS:
            dia = proximo_dia_util(n)
            usuario = usuarios[email]
            try:
                reservas.criar(usuario.id, usuario.papel, salas[codigo].id,
                               datetime.combine(dia, time.fromisoformat(ini)),
                               datetime.combine(dia, time.fromisoformat(fim)),
                               participantes, finalidade)
                criadas += 1
            except ErroDeNegocio:
                continue

    click.echo(
        f"Seed concluído: {Usuario.query.count()} usuários, {Sala.query.count()} salas, "
        f"{Reserva.query.count()} reservas ({criadas} novas)."
    )
    # Dia das reservas encostadas do LAB-B204: bom para ver a R4 na prática.
    primeira = (Reserva.query.filter_by(sala_id=salas["LAB-B204"].id)
                .order_by(Reserva.inicio).first())
    dia_demo = primeira.inicio.date() if primeira else proximo_dia_util(1)
    click.echo(f"Dia da demo: {dia_demo.isoformat()}")
    if dia_demo <= relogio.agora().date():
        click.echo("Atenção: esse dia já passou. Apague instance/reservalab.db e rode o seed de novo.")

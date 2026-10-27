from datetime import datetime, time, timedelta

from app.models import Reserva

ABERTURA = time(7, 30)
FECHAMENTO = time(22, 30)


def calcular_faixas(dia, ocupacoes):
    """Função pura: divide a janela de funcionamento do dia em ocupado e livre.

    ocupacoes: lista de (inicio, fim, reserva_id) das reservas confirmadas.
    Não acessa banco nem relógio: mesma entrada, mesma saída.
    """
    abertura = datetime.combine(dia, ABERTURA)
    fechamento = datetime.combine(dia, FECHAMENTO)

    ocupado, livre = [], []
    cursor = abertura  # até onde a janela já foi percorrida
    for inicio, fim, reserva_id in sorted(ocupacoes):
        inicio, fim = max(inicio, abertura), min(fim, fechamento)
        if inicio >= fim:
            continue  # fora da janela
        if inicio > cursor:
            livre.append({"inicio": cursor, "fim": inicio})
        ocupado.append({"inicio": inicio, "fim": fim, "reserva_id": reserva_id})
        cursor = max(cursor, fim)

    if cursor < fechamento:
        livre.append({"inicio": cursor, "fim": fechamento})
    return ocupado, livre


def da_sala(sala, dia):
    """Busca as reservas confirmadas do dia e monta a resposta da disponibilidade."""
    reservas = Reserva.query.filter(
        Reserva.sala_id == sala.id,
        Reserva.status == "confirmada",
        Reserva.inicio < datetime.combine(dia + timedelta(days=1), time.min),
        Reserva.fim > datetime.combine(dia, time.min),
    ).all()
    ocupado, livre = calcular_faixas(dia, [(r.inicio, r.fim, r.id) for r in reservas])
    if not sala.ativa:
        livre = []  # R6: sala inativa não pode ser reservada, então nada está livre
    return {"sala": sala, "data": dia.isoformat(), "ocupado": ocupado, "livre": livre}

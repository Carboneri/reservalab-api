from app.extensions import db

TIPOS_SALA = ("laboratorio", "sala_aula", "auditorio")


class Sala(db.Model):
    __tablename__ = "salas"
    __table_args__ = (
        db.CheckConstraint("capacidade > 0", name="ck_sala_capacidade"),
        # Sem AUTOINCREMENT o SQLite reaproveita o maior id depois de uma exclusão.
        {"sqlite_autoincrement": True},
    )

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), nullable=False, unique=True)
    nome = db.Column(db.String(100), nullable=False)
    bloco = db.Column(db.String(10), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    capacidade = db.Column(db.Integer, nullable=False)
    # No banco é "projetor,ar-condicionado"; na API é uma lista (ver propriedade).
    recursos_texto = db.Column("recursos", db.String(255), nullable=False, default="")
    ativa = db.Column(db.Boolean, nullable=False, default=True)

    # R10: excluir a sala apaga junto o histórico de reservas dela.
    # O bloqueio quando há reservas futuras confirmadas fica no serviço.
    reservas = db.relationship("Reserva", back_populates="sala", cascade="all, delete-orphan")

    @property
    def recursos(self):
        return [r for r in (self.recursos_texto or "").split(",") if r]

    @recursos.setter
    def recursos(self, lista):
        self.recursos_texto = ",".join(r.strip() for r in lista if r.strip())

    def __marshallable__(self):
        # fields.Url chama url_for("sala", **este_dict); a rota espera "sala_id".
        return {"sala_id": self.id}

    def __repr__(self):
        return f"<Sala {self.codigo}>"

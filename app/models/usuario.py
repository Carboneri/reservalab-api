from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.services import relogio

PAPEIS = ("aluno", "professor", "admin")


class Usuario(db.Model):
    __tablename__ = "usuarios"
    __table_args__ = {"sqlite_autoincrement": True}  # ids excluídos não são reaproveitados

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    papel = db.Column(db.String(20), nullable=False, default="aluno")
    criado_em = db.Column(db.DateTime, nullable=False, default=lambda: relogio.agora())

    reservas = db.relationship("Reserva", back_populates="usuario")

    # Guardamos só o hash: nem o banco nem a API conhecem a senha original.
    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def __repr__(self):
        return f"<Usuario {self.email} ({self.papel})>"

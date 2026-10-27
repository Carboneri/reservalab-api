from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy

# Criadas sem app: create_app() as liga depois com init_app (application factory).
db = SQLAlchemy()
jwt = JWTManager()

# init_db.py
from app import db, Usuario
from werkzeug.security import generate_password_hash

def crear_usuarios():
    if not Usuario.query.filter_by(nombre="Mikel").first():
        db.session.add(Usuario(nombre="Mikel", password=generate_password_hash("0022")))
    if not Usuario.query.filter_by(nombre="Monica").first():
        db.session.add(Usuario(nombre="Monica", password=generate_password_hash("0022")))
    db.session.commit()
    print("Usuarios iniciales creados.")

if __name__ == "__main__":
    crear_usuarios()

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Cambia esto en producción

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ahorro.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.template_filter('moneda')
def moneda_filter(valor):
    try:
        valor = float(valor)
        return "{:,.2f} €".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return valor

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    movimientos = db.relationship('Movimiento', backref='usuario', lazy=True)
    ahorro_inicial = db.Column(db.Float, default=0)

class Objetivo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Float, nullable=False)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    importe = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(100))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

class Anuncio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    url = db.Column(db.String(400), nullable=True)
    comentario = db.Column(db.String(500), nullable=True)
    creado_por = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    marcado_interesante = db.Column(db.Integer, default=0)  # 0: sin marcar, 1: sí, -1: no
    notificado = db.Column(db.Boolean, default=False)
    archivado = db.Column(db.Boolean, default=False)

class Notificacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mensaje = db.Column(db.String(300), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    leida = db.Column(db.Boolean, default=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/crear_usuario')
def crear_usuario():
    if Usuario.query.filter_by(nombre="Mikel").first() is None:
        db.session.add(Usuario(nombre="Mikel", password=generate_password_hash("0022")))
    if Usuario.query.filter_by(nombre="Monica").first() is None:
        db.session.add(Usuario(nombre="Monica", password=generate_password_hash("0022")))
    db.session.commit()
    return "Usuarios creados (recuerda borrar esta ruta luego)"

@app.route('/cambiar_password/<nombre>/<nueva>')
def cambiar_password(nombre, nueva):
    user = Usuario.query.filter_by(nombre=nombre).first()
    if user:
        user.password = generate_password_hash(nueva)
        db.session.commit()
        return f'Contraseña de {nombre} actualizada.'
    return 'Usuario no encontrado.'

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nombre = request.form['usuario']
        clave = request.form['clave']
        user = Usuario.query.filter_by(nombre=nombre).first()
        if user and check_password_hash(user.password, clave):
            session['usuario_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contraseña incorrecta.', 'danger')
    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    user = Usuario.query.get(session['usuario_id'])
    objetivo = Objetivo.query.order_by(Objetivo.id.desc()).first()

    if request.method == 'POST' and 'objetivo' in request.form:
        try:
            monto = float(request.form['objetivo'])
            if monto > 0 and not objetivo:
                objetivo = Objetivo(monto=monto, creado_por=user.id)
                db.session.add(objetivo)
                db.session.commit()
                flash(f"Objetivo guardado: {monto:.2f} €", "success")
        except ValueError:
            flash("Introduce un objetivo válido.", "danger")

    if request.method == 'POST' and 'ahorro_inicial' in request.form and objetivo:
        try:
            ahorro_inicial = float(request.form['ahorro_inicial'])
            if ahorro_inicial >= 0 and user.ahorro_inicial == 0:
                user.ahorro_inicial = ahorro_inicial
                movimiento = Movimiento(importe=ahorro_inicial, descripcion='Ahorro inicial', usuario_id=user.id)
                db.session.add(movimiento)
                db.session.commit()
                flash(f"Ahorro inicial añadido: {ahorro_inicial:.2f} €", "success")
        except ValueError:
            flash("Introduce un ahorro inicial válido.", "danger")

    if request.method == 'POST' and 'ingreso' in request.form and objetivo:
    try:
        importe = float(request.form['ingreso'])
        desc = request.form.get('descripcion', '')
        if importe > 0:
            movimiento = Movimiento(importe=importe, descripcion=desc, usuario_id=user.id)
            db.session.add(movimiento)
            db.session.commit()
            flash(f"Aporte añadido: {importe:.2f} €", "success")
            # NOTIFICAR a TODOS los usuarios, incluido el que hace el aporte
            usuarios = Usuario.query.all()
            for destinatario in usuarios:
                if desc:
                    mensaje = f"{user.nombre} ha hecho un aporte de {importe:,.2f} €: {desc}"
                else:
                    mensaje = f"{user.nombre} ha hecho un aporte de {importe:,.2f} €"
                noti = Notificacion(mensaje=mensaje, usuario_id=destinatario.id)
                db.session.add(noti)
            db.session.commit()
    except ValueError:
        flash("Introduce un valor válido.", "danger")

    total_ahorrado = db.session.query(db.func.sum(Movimiento.importe)).scalar() or 0
    objetivo_30 = objetivo.monto * 0.3 if objetivo else 0

    todos_los_movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).all()
    movimientos_render = []
    for mov in todos_los_movimientos:
        movimientos_render.append({
            'id': mov.id,
            'importe': mov.importe,
            'descripcion': mov.descripcion,
            'autor': mov.usuario.nombre,
            'fecha': mov.fecha.strftime('%d/%m/%Y %H:%M')
        })

    movs = Movimiento.query.order_by(Movimiento.fecha.asc()).all()
    fechas = []
    acumulado = []
    suma = 0
    aportes_por_mes = defaultdict(float)
    for mov in movs:
        suma += mov.importe
        fechas.append(mov.fecha.strftime('%d/%m/%Y %H:%M'))
        acumulado.append(suma)
        mes = mov.fecha.strftime('%Y-%m')
        aportes_por_mes[mes] += mov.importe
    num_meses = len(aportes_por_mes)
    promedio_mensual = sum(aportes_por_mes.values()) / num_meses if num_meses > 0 else 0
    faltante = objetivo_30 - total_ahorrado if objetivo_30 > total_ahorrado else 0
    meses_restantes = int(faltante / promedio_mensual + 0.999) if promedio_mensual > 0 and faltante > 0 else 0

    simulado = request.args.get('simulado', type=float)
    meses_simulado = None
    if simulado and simulado > 0 and objetivo_30 > total_ahorrado:
        faltante_sim = objetivo_30 - total_ahorrado
        meses_simulado = int(faltante_sim / simulado + 0.999)

    # --------- NOTIFICACIONES NUEVAS ---------
    notificaciones_nuevas = Notificacion.query.filter_by(usuario_id=user.id, leida=False).all()
    for notif in notificaciones_nuevas:
        notif.leida = True
    db.session.commit()

    return render_template('dashboard.html',
        usuario=user.nombre,
        user=user,
        objetivo=objetivo.monto if objetivo else None,
        objetivo_30=objetivo_30,
        total_ahorrado=total_ahorrado,
        todos_los_movimientos=movimientos_render,
        fechas=fechas,
        acumulado=acumulado,
        promedio_mensual=promedio_mensual,
        meses_restantes=meses_restantes,
        simulado=simulado,
        meses_simulado=meses_simulado,
        notificaciones_nuevas=notificaciones_nuevas
    )

@app.route('/logout')
def logout():
    session.pop('usuario_id', None)
    return redirect(url_for('login'))

@app.route('/editar_movimiento/<int:mov_id>', methods=['GET', 'POST'])
def editar_movimiento(mov_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    movimiento = Movimiento.query.get_or_404(mov_id)
    if movimiento.usuario_id != session['usuario_id']:
        abort(403)
    if request.method == 'POST':
        try:
            importe = float(request.form['importe'])
            descripcion = request.form['descripcion']
            if importe >= 0:
                movimiento.importe = importe
                movimiento.descripcion = descripcion
                db.session.commit()
                flash('Movimiento actualizado correctamente.', 'success')
                return redirect(url_for('dashboard'))
        except ValueError:
            flash("Introduce un valor válido.", "danger")
    return render_template('editar_movimiento.html', movimiento=movimiento)

@app.route('/anuncio/nuevo', methods=['GET', 'POST'])
def nuevo_anuncio():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    user = Usuario.query.get(session['usuario_id'])
    otros = Usuario.query.filter(Usuario.id != user.id).first()
    if not otros:
        flash("No hay otro usuario para enviar el anuncio.", "danger")
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        titulo = request.form['titulo']
        url_ = request.form['url']
        comentario = request.form['comentario']
        anuncio = Anuncio(
            titulo=titulo,
            url=url_,
            comentario=comentario,
            creado_por=user.id,
            destinatario_id=otros.id
        )
        db.session.add(anuncio)
        db.session.commit()
        notificacion = Notificacion(
            mensaje=f"{user.nombre} ha publicado un nuevo anuncio de vivienda.",
            usuario_id=otros.id
        )
        db.session.add(notificacion)
        db.session.commit()
        flash('Anuncio enviado.', 'success')
        return render_template("anuncio_exito.html")
    return render_template("nuevo_anuncio.html")

@app.route('/anuncios', methods=['GET', 'POST'])
def anuncios():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    user = Usuario.query.get(session['usuario_id'])
    anuncios_recibidos = Anuncio.query.filter_by(destinatario_id=user.id, archivado=False)\
    .order_by(Anuncio.fecha_creacion.desc()).all()
    notificaciones = Anuncio.query.filter_by(creado_por=user.id, notificado=False, archivado=False)\
    .filter(Anuncio.marcado_interesante != 0).all()


    if request.method == 'POST':
        anuncio_id = int(request.form['anuncio_id'])
        accion = request.form['accion']  # 'si' o 'no'
        anuncio = Anuncio.query.get(anuncio_id)
        if anuncio and anuncio.destinatario_id == user.id:
            anuncio.marcado_interesante = 1 if accion == 'si' else -1
            # Añadir notificación para el creador del anuncio
            creador = Usuario.query.get(anuncio.creado_por)
            mensaje = (
                f"{user.nombre} ha marcado tu anuncio '{anuncio.titulo}' como "
                + ("interesante ✅." if accion == "si" else "NO interesante ❌.")
            )
            noti = Notificacion(mensaje=mensaje, usuario_id=creador.id)
            db.session.add(noti)
            db.session.commit()
            flash('Respuesta enviada.', 'success')
        return redirect(url_for('anuncios'))

    return render_template('anuncios.html', anuncios_recibidos=anuncios_recibidos, notificaciones=notificaciones)

@app.route('/limpiar_anuncios_recibidos', methods=['POST'])
def limpiar_anuncios_recibidos():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    user_id = session['usuario_id']
    anuncios_recibidos = Anuncio.query.filter_by(destinatario_id=user_id, archivado=False).all()
    for anuncio in anuncios_recibidos:
        anuncio.archivado = True
    db.session.commit()
    flash("Tus anuncios recibidos han sido archivados.", "success")
    return redirect(url_for('dashboard'))

@app.route('/limpiar_anuncios_enviados', methods=['POST'])
def limpiar_anuncios_enviados():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    user_id = session['usuario_id']
    anuncios_enviados = Anuncio.query.filter_by(creado_por=user_id, archivado=False).all()
    for anuncio in anuncios_enviados:
        anuncio.archivado = True
    db.session.commit()
    flash("Tus anuncios enviados han sido archivados.", "success")
    return redirect(url_for('dashboard'))

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

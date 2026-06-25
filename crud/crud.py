from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import os, logging, ssl, certifi
import paho.mqtt.publish as publish
from functools import wraps
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

logging.basicConfig(format='%(asctime)s - CRUD - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
app.config["MYSQL_USER"] = os.environ["MYSQL_USER"]
app.config["MYSQL_PASSWORD"] = os.environ["MYSQL_PASSWORD"]
app.config["MYSQL_DB"] = os.environ["MYSQL_DB"]
app.config["MYSQL_HOST"] = os.environ["MYSQL_HOST"]
app.config['PERMANENT_SESSION_LIFETIME']=180
mysql = MySQL(app)

def publicar_comando(topico, payload):
    """Abre conexión MQTTS, publica una orden y cierra"""
    publish.single(
        topic=topico,
        payload=payload,
        hostname=os.environ["SERVIDOR"],
        port=int(os.environ["PUERTO_MQTTS"]),
        auth={"username": os.environ["MQTT_USR"], "password": os.environ["MQTT_PASS"]},
        tls={"ca_certs": certifi.where(), "tls_version": ssl.PROTOCOL_TLS_CLIENT},
    )

# rutas

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/registrar", methods=["GET", "POST"])
def registrar():
    """Registrar usuario"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("usuario"):
            return "el campo usuario es oblicatorio"

        # Ensure password was submitted
        elif not request.form.get("password"):
            return "el campo contraseña es oblicatorio"

        passhash=generate_password_hash(request.form.get("password"), method='scrypt', salt_length=16)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (usuario, hash) VALUES (%s,%s)", (request.form.get("usuario"), passhash[17:]))
        if mysql.connection.affected_rows():
            flash('Se agregó un usuario')  # usa sesión
            logging.info("se agregó un usuario")
        mysql.connection.commit()
        return redirect(url_for('home'))

    return render_template('registrar.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("usuario"):
            return "el campo usuario es oblicatorio"
        # Ensure password was submitted
        elif not request.form.get("password"):
            return "el campo contraseña es oblicatorio"

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario LIKE %s", (request.form.get("usuario"),))
        rows=cur.fetchone()
        if(rows):
            if (check_password_hash('scrypt:32768:8:1$' + rows[2],request.form.get("password"))):
                session.permanent = True
                session["user_id"]=request.form.get("usuario")
                logging.info("se autenticó correctamente")
                return redirect(url_for('home'))
            else:
                flash('usuario o contraseña incorrecto')
                return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/')
@require_login
def home():
    return render_template('home.html')

@app.route('/agenda')
@require_login
def agenda():
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM contactos')
    datos = cur.fetchall()
    cur.close()
    return render_template('index.html', contactos = datos)

@app.route('/add_contact', methods=['POST'])
@require_login
def add_contact():
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO contactos (nombre, tel, email) VALUES (%s,%s,%s)"
                    , (nombre, tel, email))
        if mysql.connection.affected_rows():
            flash('Se agregó un contacto')  # usa sesión
            logging.info("se agregó un contacto")
            mysql.connection.commit()
    return redirect(url_for('agenda'))

@app.route('/borrar/<string:id>', methods = ['GET'])
@require_login
def borrar_contacto(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM contactos WHERE id = %s', (id,))
    if mysql.connection.affected_rows():
        flash('Se eliminó un contacto')  # usa sesión
        logging.info("se eliminó un contacto")
        mysql.connection.commit()
    return redirect(url_for('agenda'))

@app.route('/editar/<id>', methods = ['GET'])
@require_login
def conseguir_contacto(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM contactos WHERE id = %s', (id,))
    datos = cur.fetchone()
    logging.info(datos)
    return render_template('editar-contacto.html', contacto = datos)

@app.route('/actualizar/<id>', methods=['POST'])
@require_login
def actualizar_contacto(id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        tel = request.form['tel']
        email = request.form['email']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE contactos SET nombre=%s, tel=%s, email=%s WHERE id=%s", (nombre, tel, email, id))
    if mysql.connection.affected_rows():
        flash('Se actualizó un contacto')  # usa sesión
        logging.info("se actualizó un contacto")
        mysql.connection.commit()
    return redirect(url_for('agenda'))

@app.route('/comandos')
@require_login
def comandos():
    cur = mysql.connection.cursor()
    cur.execute('SELECT id, sensor_id, mac, nombre, topico FROM sensores_remotos.nodos')
    nodos = cur.fetchall()
    cur.close()
    return render_template('comandos.html', nodos=nodos)

@app.route('/comandos/enviar', methods=['POST'])
@require_login
def enviar_comando():
    sensor_id = request.form.get('sensor_id')
    comando = request.form.get('comando')

    if not sensor_id:
        flash('Seleccioná un nodo destinatario')
        return redirect(url_for('comandos'))

    # Validación y lectura del valor según el comando
    if comando == 'setpoint':
        try:
            valor = str(int(request.form.get('valor_setpoint')))
        except (TypeError, ValueError):
            flash('El setpoint debe ser un número entero')
            return redirect(url_for('comandos'))
    elif comando == 'destello':
        valor = request.form.get('valor_destello')
        if valor not in ('on', 'off'):
            flash('El destello sólo acepta on u off')
            return redirect(url_for('comandos'))
    else:
        flash('Comando desconocido')
        return redirect(url_for('comandos'))

    # Buscar el tópico de comandos del nodo elegido
    cur = mysql.connection.cursor()
    cur.execute('SELECT topico FROM sensores_remotos.nodos WHERE sensor_id = %s', (sensor_id,))
    fila = cur.fetchone()
    cur.close()
    if not fila:
        flash('No se encontró el nodo seleccionado')
        return redirect(url_for('comandos'))

    topico = fila[0]
    payload = "{}:{}".format(comando, valor)
    try:
        publicar_comando(topico, payload)
        flash("Orden enviada a {}: {}".format(sensor_id, payload))
        logging.info("comando publicado en %s -> %s", topico, payload)
    except Exception:
        flash('No se pudo enviar la orden')
        logging.exception("error al publicar comando MQTTS")
    return redirect(url_for('comandos'))

@app.route('/nodos/agregar', methods=['POST'])
@require_login
def agregar_nodo():
    sensor_id = request.form['sensor_id']
    mac = request.form['mac']
    nombre = request.form['nombre']
    topico = request.form['topico']
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO sensores_remotos.nodos (sensor_id, mac, nombre, topico) VALUES (%s,%s,%s,%s)",
                (sensor_id, mac, nombre, topico))
    if mysql.connection.affected_rows():
        flash('Se agregó un nodo')
        logging.info("se agregó un nodo")
        mysql.connection.commit()
    return redirect(url_for('comandos'))

@app.route('/nodos/borrar/<string:id>', methods=['GET'])
@require_login
def borrar_nodo(id):
    cur = mysql.connection.cursor()
    cur.execute('DELETE FROM sensores_remotos.nodos WHERE id = %s', (id,))
    if mysql.connection.affected_rows():
        flash('Se eliminó un nodo')
        logging.info("se eliminó un nodo")
        mysql.connection.commit()
    return redirect(url_for('comandos'))

@app.route("/logout")
@require_login
def logout():
    session.clear()
    logging.info("el usuario {} cerró su sesión".format(session.get("user_id")))
    return redirect(url_for('login'))

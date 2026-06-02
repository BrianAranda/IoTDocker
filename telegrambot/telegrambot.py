from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import logging, os, asyncio, aiomysql, traceback, locale
import matplotlib.pyplot as plt
from io import BytesIO
import aiomqtt
import ssl

token=os.environ["TB_TOKEN"]

logging.basicConfig(format='%(asctime)s - TelegramBot - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("se conectó: " + str(update.message.from_user.id))
    if update.message.from_user.first_name:
        nombre=update.message.from_user.first_name
    else:
        nombre=""
    if update.message.from_user.last_name:
        apellido=update.message.from_user.last_name
    else:
        apellido=""
    kb = [["temperatura"],["humedad"],["gráfico temperatura"],["gráfico humedad"]]
    await context.bot.send_message(update.message.chat.id, text="Bienvenido al Bot "+ nombre + " " + apellido,reply_markup=ReplyKeyboardMarkup(kb))

async def about(update: Update, context):
    await context.bot.send_message(update.message.chat.id, text="Este bot fue creado para el curso de IoT FIO")

async def kill(update: Update, context):
    logging.info(context.args)
    if context.args and context.args[0] == '@e':
        await context.bot.send_animation(update.message.chat.id, "CgACAgQAAxkBAAMJahiDOvbBMZVUYF4F1dYkgmKzXToAAg0DAAKBxQ1TckSOTVgP--g7BA")
        await asyncio.sleep(6)
        await context.bot.send_message(update.message.chat.id, text="noooooo")
    else:
        await context.bot.send_message(update.message.chat.id, text="☠️☠️☠️☠️☠️")
        
async def medicion(update: Update, context):
    logging.info(update.message.text)
    sql = f"SELECT timestamp, {update.message.text} FROM mediciones ORDER BY timestamp DESC LIMIT 1"
    conn = await aiomysql.connect(host=os.environ["MARIADB_SERVER"], port=3306,
                                    user=os.environ["MARIADB_USER"],
                                    password=os.environ["MARIADB_USER_PASS"],
                                    db=os.environ["MARIADB_DB"])
    async with conn.cursor() as cur:
        await cur.execute(sql)
        r = await cur.fetchone()
        if update.message.text == 'temperatura':
            unidad = 'ºC'
        else:
            unidad = '%'
        await context.bot.send_message(update.message.chat.id,
                                    text="La última {} es de {} {},\nregistrada a las {:%H:%M:%S %d/%m/%Y}"
                                    .format(update.message.text, str(r[1]).replace('.',','), unidad, r[0]))
        logging.info("La última {} es de {} {}, medida a las {:%H:%M:%S %d/%m/%Y}".format(update.message.text, r[1], unidad, r[0]))
    conn.close()

async def graficos(update: Update, context):
    logging.info(update.message.text)
    sql = f"""SELECT timestamp, {update.message.text.split()[1]}
            FROM (
                SELECT timestamp, {update.message.text.split()[1]},
                    ROW_NUMBER() OVER (ORDER BY id) AS rn
                FROM mediciones
                WHERE timestamp >= NOW() - INTERVAL 1 DAY
                AND sensor_id LIKE 'sensor_1'
            ) AS t
            WHERE rn % 2 = 0
            ORDER BY timestamp;"""
    conn = await aiomysql.connect(host=os.environ["MARIADB_SERVER"], port=3306,
                                    user=os.environ["MARIADB_USER"],
                                    password=os.environ["MARIADB_USER_PASS"],
                                    db=os.environ["MARIADB_DB"])
    async with conn.cursor() as cur:
        await cur.execute(sql)
        filas = await cur.fetchall()

        fig, ax = plt.subplots(figsize=(7, 4))
        fecha,var=zip(*filas)
        ax.plot(fecha,var)
        ax.grid(True, which='both')
        ax.set_title(update.message.text, fontsize=14, verticalalignment='bottom')
        ax.set_xlabel('fecha')
        ax.set_ylabel('unidad')

        buffer = BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format='png')
        plt.close()
        buffer.seek(0)
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buffer)
        buffer.close()
    conn.close()

async def enviar_orden_mqtt(comando, valor):
    """
    Se conecta a Mosquitto y publica una orden para la Raspberry.
    Recibe el 'comando' (ej. setpoint, rele) y el 'valor' (ej. 25, on).
    """
    
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    servidor = os.environ["SERVIDOR"]
    usuario = os.environ["MQTT_USR"]
    password = os.environ["MQTT_PASS"]
    puerto = os.environ["PUERTO_MQTTS"]
    
    topico_ordenes = os.environ.get("TOPICO_PUB", "iot/termostato/comandos")

    try:
        async with aiomqtt.Client(
            hostname=servidor,
            port=puerto,
            username=usuario,
            password=password,
            tls_context=tls_context
        ) as client:
            payload = f"{comando}:{valor}"
            await client.publish(topico_ordenes, payload=payload)
            logging.info(f"Orden MQTT enviada con éxito: {payload}")
            return True

    except Exception as e:
        logging.error(f"Error al enviar orden MQTT: {e}")
        return False

async def comando_setpoint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        valor = context.args[0]
        exito = await enviar_orden_mqtt("setpoint", valor)
        if exito:
            await update.message.reply_text(f"Orden enviada: Setpoint actualizado a {valor}°C")
        else:
            await update.message.reply_text("Error al intentar enviar la orden")
    else:
        await update.message.reply_text("Uso correcto: /setpoint <valor>")

async def comando_rele(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        valor = context.args[0].lower()
        if valor in ['on', 'off']:
            exito = await enviar_orden_mqtt("rele", valor)
            if exito:
                await update.message.reply_text(f"Orden enviada: Relé en modo {valor.upper()}")
            else:
                await update.message.reply_text("Error al intentar enviar la orden.")
        else:
             await update.message.reply_text("El valor del relé debe ser 'on' u 'off'.")
    else:
        await update.message.reply_text("Uso correcto: /rele <on/off>")

async def comando_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        valor = context.args[0]
        exito = await enviar_orden_mqtt("modo", valor)
        if exito:
            await update.message.reply_text(f"Orden enviada: Modo cambiado a {valor}")
        else:
            await update.message.reply_text("Error de red al intentar enviar la orden.")
    else:
        await update.message.reply_text("Uso correcto: /modo <valor>")

async def comando_periodo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        valor = context.args[0]
        exito = await enviar_orden_mqtt("periodo", valor)
        if exito:
            await update.message.reply_text(f"Orden enviada: Período actualizado a {valor}")
        else:
            await update.message.reply_text("Error de red al intentar enviar la orden.")
    else:
        await update.message.reply_text("Uso correcto: /periodo <valor>")

async def comando_destello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        valor = context.args[0]
        exito = await enviar_orden_mqtt("destello", valor)
        if exito:
            await update.message.reply_text(f"Orden enviada: Destello actualizado a {valor}")
        else:
            await update.message.reply_text("Error de red al intentar enviar la orden.")
    else:
        await update.message.reply_text("Uso correcto: /destello <valor>")

def main():
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('about', about))
    application.add_handler(CommandHandler('kill', kill))

    application.add_handler(CommandHandler('setpoint', comando_setpoint))
    application.add_handler(CommandHandler('rele', comando_rele))
    application.add_handler(CommandHandler('modo', comando_modo))
    application.add_handler(CommandHandler('periodo', comando_periodo))
    application.add_handler(CommandHandler('destello', comando_destello))

    application.add_handler(MessageHandler(filters.Regex("^(temperatura|humedad)$"), medicion))
    application.add_handler(MessageHandler(filters.Regex("^(gráfico temperatura|gráfico humedad)$"), graficos))
    application.run_polling()

if __name__ == '__main__':
    main()

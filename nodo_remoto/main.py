"""
Se suscribe al tópico de comandos "led" y enciende/apaga un LED físico según reciba el mensaje "encender" o "apagar".

Cada vez que procesa un comando, publica el estado actual del LED en el subtópico "led/estado", para que el indicador luminoso del dashboard de Node-RED se actualice.

Publica lecturas de temperatura y humedad al tópico "nodered", que Node-RED almacena en la base de datos y muestra en los gauges.

Variables de entorno: SERVIDOR, PUERTO_MQTTS, MQTT_USR, MQTT_PASS
"""

import os
import ssl
import json
import time
import logging

import paho.mqtt.client as mqtt

try:
    from gpiozero import LED
except Exception:
    LED = None

logging.basicConfig(
    format="%(asctime)s - nodo remoto - %(levelname)s:%(message)s",
    level=logging.INFO,
    datefmt="%d/%m/%Y %H:%M:%S %z",
)

SERVIDOR = os.environ["SERVIDOR"]
PUERTO_MQTTS = int(os.environ["PUERTO_MQTTS"])
MQTT_USR = os.environ["MQTT_USR"]
MQTT_PASS = os.environ["MQTT_PASS"]

TOPICO_COMANDO = "led/orden"    # switch del dashboard -> nodo remoto
TOPICO_ESTADO = "led/estado"    # nodo remoto -> indicador luminoso
TOPICO_SENSOR = "nodered"       # lecturas de temp/humedad

LED_PIN = 17

led = LED(LED_PIN) if LED else None

def aplicar_estado(comando: str) -> str:
    comando = comando.strip().lower()
    if comando == "encender":
        if led:
            led.on()
        return "encender"
    elif comando == "apagar":
        if led:
            led.off()
        return "apagar"
    else:
        logging.warning("Comando desconocido: %s", comando)
        if led:
            return "encender" if led.is_lit else "apagar"
        return "apagar"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Conectado al broker MQTT")
        client.subscribe(TOPICO_COMANDO)
        logging.info("Suscrito a '%s'", TOPICO_COMANDO)
    else:
        logging.error("Fallo de conexión MQTT, código %s", rc)

def on_message(client, userdata, msg):
    comando = msg.payload.decode("utf-8")
    logging.info("Comando recibido en '%s': %s", msg.topic, comando)

    estado = aplicar_estado(comando)

    client.publish(TOPICO_ESTADO, estado, qos=1, retain=True)
    logging.info("Estado publicado en '%s': %s", TOPICO_ESTADO, estado)


def leer_sensor():
    try:
        import board
        import adafruit_dht

        dht = adafruit_dht.DHT22(board.D4)
        return dht.temperature, dht.humidity
    except Exception:
        return None, None

def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USR, MQTT_PASS)

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()
    client.tls_set_context(tls_context)

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(SERVIDOR, PUERTO_MQTTS, keepalive=60)
    client.loop_start()

    try:
        while True:
            temp, hum = leer_sensor()
            if temp is not None and hum is not None:
                payload = json.dumps({"temperatura": round(temp, 1),
                                      "humedad": round(hum, 1)})
                client.publish(TOPICO_SENSOR, payload, qos=1)
                logging.info("Sensor publicado en '%s': %s", TOPICO_SENSOR, payload)
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("Cerrando nodo remoto...")
    finally:
        client.loop_stop()
        client.disconnect()
        if led:
            led.close()

if __name__ == "__main__":
    main()

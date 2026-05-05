import asyncio
import os
import ssl
import logging
import aiomqtt

logging.basicConfig(
    format='%(asctime)s - %(taskName)s - %(levelname)s: %(message)s', 
    level=logging.INFO, 
    datefmt='%d/%m/%Y %H:%M:%S %z'
)

async def atender_topico_1(mensaje):
    logging.info(f"Mensaje de {mensaje.topic}: {mensaje.payload.decode('utf-8')}")

async def atender_topico_2(mensaje):
    logging.info(f"Mensaje de {mensaje.topic}: {mensaje.payload.decode('utf-8')}")

async def incrementar_contador(estado):
    while True:
        await asyncio.sleep(3)
        estado["contador"] += 1
        logging.info(f"Contador en: {estado['contador']}")

async def publicar_contador(client, topico_pub, estado):
    while True:
        await asyncio.sleep(5)
        valor_actual = estado["contador"]
        await client.publish(topico_pub, payload=str(valor_actual))
        logging.info(f"Se publicó: {valor_actual}")

async def main():
    servidor = os.environ.get('SERVIDOR')
    topico_sub1 = os.environ.get('TOPICO_SUB1')
    topico_sub2 = os.environ.get('TOPICO_SUB2')
    topico_pub = os.environ.get('TOPICO_PUB')

    estado = {"contador": 0}

    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.verify_mode = ssl.CERT_REQUIRED
    tls_context.check_hostname = True
    tls_context.load_default_certs()

    async with aiomqtt.Client(
        servidor,
        port=8883,
        tls_context=tls_context
    ) as client:
        await client.subscribe(topico_sub1)
        await client.subscribe(topico_sub2)
        logging.info(f"Subscrito a: {topico_sub1} y {topico_sub2}")

        asyncio.create_task(incrementar_contador(estado), name="Incrementar contador")
        asyncio.create_task(publicar_contador(client, topico_pub, estado), name="Publicar contador")

        async for message in client.messages:
            if message.topic.matches(topico_sub1):
                asyncio.create_task(atender_topico_1(message), name="Atender Tópico 1")
            elif message.topic.matches(topico_sub2):
                asyncio.create_task(atender_topico_2(message), name="Atender Tópico 2")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("¿A papá mono con banana verde 🍌🐒?")

import asyncio
import json
import os
import random
import uuid
from datetime import datetime, timezone

from gmqtt import Client as MQTTClient

MQTT_HOST = os.getenv("MQTT_HOST", "lse.dev.br")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None

TOPIC_ELEC = "scgdi/motor/electrical"
TOPIC_ENV  = "scgdi/motor/environment"
TOPIC_VIB  = "scgdi/motor/vibration"

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

class MQTTChannel:
    def __init__(self):
        self.client = MQTTClient(uuid.uuid4().hex)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe

    def on_connect(self, client, flags, rc, properties):
        print(f"[MQTT] conectado em {MQTT_HOST}:{MQTT_PORT} rc={rc}")

    def on_message(self, client, topic, payload, qos, properties):
        pass

    def on_disconnect(self, client, packet, exc=None):
        print("[MQTT] desconectado")

    def on_subscribe(self, client, mid, qos, properties):
        print("[MQTT] subscribed mid=", mid)

    async def connect(self):
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.set_auth_credentials(MQTT_USERNAME, MQTT_PASSWORD)
        await self.client.connect(MQTT_HOST, MQTT_PORT)

    async def send_electrical(self):
        # Envia a cada ~5s
        while True:
            payload = {
                "timestamp": now_iso(),
                "voltage": {
                    "a": 220.0 + random.uniform(-2.0, 2.0),
                    "b": 220.0 + random.uniform(-2.0, 2.0),
                    "c": 220.0 + random.uniform(-2.0, 2.0),
                },
                "current": {
                    "a": 10.0 + random.uniform(-0.3, 0.3),
                    "b": 10.0 + random.uniform(-0.3, 0.3),
                    "c": 10.0 + random.uniform(-0.3, 0.3),
                },
                "power": {
                    "active": 4500 + random.uniform(-50, 50),
                    "reactive": 500 + random.uniform(-30, 30),
                    "apparent": 4600 + random.uniform(-50, 50),
                },
                "energy": {
                    "active": 10000 + random.uniform(0, 5),
                    "reactive": 1200 + random.uniform(0, 2),
                    "apparent": 10200 + random.uniform(0, 5),
                },
                "powerFactor": 0.95 + random.uniform(-0.01, 0.01),
                "frequency": 60.0 + random.uniform(-0.05, 0.05),
            }
            self.client.publish(TOPIC_ELEC, json.dumps(payload))
            await asyncio.sleep(5)

    async def send_environment(self):
        # Envia a cada ~60s
        while True:
            payload = {
                "timestamp": now_iso(),
                "temperature": 34.0 + random.uniform(-1.0, 1.0),
                "humidity": 55.0 + random.uniform(-3.0, 3.0),
                "caseTemperature": 40.0 + random.uniform(-2.0, 2.0),
            }
            self.client.publish(TOPIC_ENV, json.dumps(payload))
            await asyncio.sleep(60)

    async def send_vibration(self):
        # Envia a cada ~5s
        while True:
            payload = {
                "timestamp": now_iso(),
                "axial": 0.10 + random.uniform(-0.03, 0.03),
                "radial": 0.12 + random.uniform(-0.03, 0.03),
            }
            self.client.publish(TOPIC_VIB, json.dumps(payload))
            await asyncio.sleep(5)

async def main():
    ch = MQTTChannel()
    await ch.connect()

    # Cria as tarefas de publicação
    asyncio.create_task(ch.send_electrical())
    asyncio.create_task(ch.send_environment())
    asyncio.create_task(ch.send_vibration())

    # Mantém rodando
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

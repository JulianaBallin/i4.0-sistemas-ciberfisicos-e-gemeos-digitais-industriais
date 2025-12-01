from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

from asyncua import ua, Server
from gmqtt import Client as MQTTClient
from loguru import logger
from dotenv import load_dotenv
from .storage import Storage
from .lds import try_register_with_lds

from asyncua.server.history_sql import HistorySQLite as UAHistorySQLite
from .utils.net import free_port, split_endpoint


from .model import (
    ElectricalPayload,
    EnvironmentPayload,
    VibrationPayload,
    SEVERITY,
    NOMINAL_VOLTAGE,
    NOMINAL_CURRENT,
    OVER_UNDER_TOL,
    CASE_TEMP_CRIT,
    TOPIC_ELEC,
    TOPIC_ENV,
    TOPIC_VIB,
    MOTOR_NODE_NAME,
)


# Utilidades

def pct_over(value: float, nominal: float) -> float:
    return (value - nominal) / nominal

def _normalize_electrical_payload(data: dict) -> dict:
    if any(k in data for k in ("Voltage", "Current", "Power")):
        v = data.get("Voltage", 0.0)
        i = data.get("Current", 0.0)
        p = data.get("Power", 0.0)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "voltage": {"a": v, "b": v, "c": v},
            "current": {"a": i, "b": i, "c": i},
            "power": {"active": p, "reactive": 0.0, "apparent": p},
            "energy": {"active": 0.0, "reactive": 0.0, "apparent": 0.0},
            "powerFactor": 0.95,
            "frequency": 60.0,
        }
    return data


def _normalize_environment_payload(data: dict) -> dict:
    if any(k in data for k in ("Temperature", "Humidity", "CaseTemperature")):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "temperature": data.get("Temperature", 0.0),
            "humidity": data.get("Humidity", 0.0),
            "caseTemperature": data.get("CaseTemperature", 0.0),
        }
    return data


def _normalize_vibration_payload(data: dict) -> dict:
    if any(k in data for k in ("Accell_X", "Accell_Y", "Accell_Z")):
        ax = float(data.get("Accell_X", 0.0))
        ry = float(data.get("Accell_Y", 0.0))
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "axial": ax,
            "radial": ry,
        }
    return data


# Servidor OPC UA + Árvore de Nós

class MotorOPCUAServer:
    def __init__(self):
        load_dotenv()
        self.endpoint = os.getenv("OPCUA_ENDPOINT", "opc.tcp://0.0.0.0:4840/scgdi/motor50cv")
        self.server_name = os.getenv("OPCUA_SERVER_NAME", "SCGDI Motor50CV Server")
        self.ns_uri = os.getenv("OPCUA_NAMESPACE_URI", "http://scgdi.local/motor50cv")
        self.db_path = os.getenv("DB_PATH", "./scgdi_history.sqlite")
        self.lds_endpoint = os.getenv("LDS_ENDPOINT", "")

        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME", "")
        self.mqtt_password = os.getenv("MQTT_PASSWORD", "")
        self.mqtt_client_id = os.getenv("MQTT_CLIENT_ID", "scgdi-motor50cv")

        self.opcua_manufacturer  = os.getenv("OPCUA_MANUFACTURER",  "Juliana LTDA")
        self.opcua_product_name  = os.getenv("OPCUA_PRODUCT_NAME",  "jbl-opcua-server")
        self.opcua_product_uri   = os.getenv("OPCUA_PRODUCT_URI",   "http://jbl.local/opcua")
        self.opcua_app_uri       = os.getenv("OPCUA_APP_URI",       "urn:juliana:opcua-server")
        self.opcua_sw_version    = os.getenv("OPCUA_SW_VERSION",    "1.0.0")
        self.opcua_build_number  = os.getenv("OPCUA_BUILD_NUMBER",  "1")

        self.storage = Storage(self.db_path)
        self.server = Server()
        self.idx = None  # namespace index

        # Variáveis OPC UA
        self.vars: Dict[str, Any] = {}

        # MQTT client
        self.mqtt: MQTTClient | None = None

    async def init(self):
        await self.storage.init()
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name(self.server_name)
        await self.server.set_build_info(
            product_uri=self.opcua_product_uri,
            manufacturer_name=self.opcua_manufacturer,
            product_name=self.opcua_product_name,
            software_version=self.opcua_sw_version,
            build_number=self.opcua_build_number,
            build_date=datetime.now(timezone.utc),
        )
        await self.server.set_application_uri(self.opcua_app_uri)

        self.server.set_server_name(f"{self.opcua_manufacturer} - {self.opcua_product_name}")
    
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self.idx = await self.server.register_namespace(self.ns_uri)

       
        objects = self.server.nodes.objects

        # Nó raiz do motor
        motor = await objects.add_object(self.idx, MOTOR_NODE_NAME)

        # Subnós
        # Electrical
        n_elec = await motor.add_object(self.idx, "Electrical")
        self.vars["VoltageA"] = await n_elec.add_variable(self.idx, "VoltageA", 0.0)
        self.vars["VoltageB"] = await n_elec.add_variable(self.idx, "VoltageB", 0.0)
        self.vars["VoltageC"] = await n_elec.add_variable(self.idx, "VoltageC", 0.0)
        self.vars["CurrentA"] = await n_elec.add_variable(self.idx, "CurrentA", 0.0)
        self.vars["CurrentB"] = await n_elec.add_variable(self.idx, "CurrentB", 0.0)
        self.vars["CurrentC"] = await n_elec.add_variable(self.idx, "CurrentC", 0.0)
        self.vars["PowerActive"] = await n_elec.add_variable(self.idx, "PowerActive", 0.0)
        self.vars["PowerReactive"] = await n_elec.add_variable(self.idx, "PowerReactive", 0.0)
        self.vars["PowerApparent"] = await n_elec.add_variable(self.idx, "PowerApparent", 0.0)
        self.vars["EnergyActive"] = await n_elec.add_variable(self.idx, "EnergyActive", 0.0)
        self.vars["EnergyReactive"] = await n_elec.add_variable(self.idx, "EnergyReactive", 0.0)
        self.vars["EnergyApparent"] = await n_elec.add_variable(self.idx, "EnergyApparent", 0.0)
        self.vars["PowerFactor"] = await n_elec.add_variable(self.idx, "PowerFactor", 0.0)
        self.vars["Frequency"] = await n_elec.add_variable(self.idx, "Frequency", 0.0)

        # Environment
        n_env = await motor.add_object(self.idx, "Environment")
        self.vars["Temperature"] = await n_env.add_variable(self.idx, "Temperature", 0.0)
        self.vars["Humidity"] = await n_env.add_variable(self.idx, "Humidity", 0.0)
        self.vars["CaseTemperature"] = await n_env.add_variable(self.idx, "CaseTemperature", 0.0)

        # Vibration
        n_vib = await motor.add_object(self.idx, "Vibration")
        self.vars["Axial"] = await n_vib.add_variable(self.idx, "Axial", 0.0)
        self.vars["Radial"] = await n_vib.add_variable(self.idx, "Radial", 0.0)

        # Tornar variáveis graváveis por servidor
        for v in self.vars.values():
            await v.set_writable()

         # --- Habilitar histórico OPC UA (variáveis + eventos) ---
        # 1) Configura storage de histórico nativo (SQLite) do asyncua
        hist = UAHistorySQLite(self.db_path)
        await hist.init()
        self.server.iserver.history_manager.set_storage(hist)

        # 2) Habilitar historização de DataChange para TODAS as variáveis do address space
        for node in self.vars.values():
            await self.server.iserver.enable_history_data_change(node)

        # 3) Habilitar historização de EVENTOS
        #    3.1 motor e Objects (como você já fazia)
        await motor.set_event_notifier([ua.EventNotifier.SubscribeToEvents])
        await self.server.iserver.enable_history_event(motor)
        objects = self.server.nodes.objects
        await objects.set_event_notifier([ua.EventNotifier.SubscribeToEvents])
        await self.server.iserver.enable_history_event(objects)

        #    3.2 Electrical/Environment/Vibration também devem gerar eventos
        for src_node in (n_elec, n_env, n_vib):
            await src_node.set_event_notifier([ua.EventNotifier.SubscribeToEvents])
            await self.server.iserver.enable_history_event(src_node)

        #    3.3 Mapa de fontes por categoria p/ usarmos no fire_event()
        self.event_sources = {
            "Electrical": n_elec,
            "Environment": n_env,
            "Vibration": n_vib,
        }
        # --- fim histórico ---

        # Preparar tipo de evento customizado (necessário antes de disparar eventos)
        await self._prepare_event_type()

        # Tentativa de registro em LDS (se configurado)
        await try_register_with_lds(self.server, self.lds_endpoint)

    async def _prepare_event_type(self):
        # Cria um tipo de evento customizado com campos adicionais
        self.evtype = await self.server.create_custom_event_type(
            self.idx,
            "SCGDIEventType",
            ua.ObjectIds.BaseEventType,
            [
                ("Category", ua.VariantType.String),
                ("Message", ua.VariantType.String),
            ],
        )

    async def fire_event(self, source_node, category: str, message: str, severity: int):
        """
        Variáveis não têm EventNotifier. Se a fonte for variável,
        emitimos pelo nó-objeto correspondente à categoria.
        """
        try:
            node_class = await source_node.read_node_class()
            if node_class == ua.NodeClass.Variable:
                emitting = self.event_sources.get(category) or self.server.nodes.objects
            else:
                emitting = source_node

            event = await self.server.get_event_generator(self.evtype, emitting)
            event.event.Severity = severity
            event.event.Message = ua.LocalizedText(message)
            event.event.Category = category
            await event.trigger()
        except Exception as e:
            logger.exception("Falha ao emitir evento (categoria=%s): %s", category, e)

        # Persistimos mesmo que o trigger falhe, para debug
        await self.storage.add_event(
            ts=datetime.now(timezone.utc).isoformat(),
            source=str((emitting if 'emitting' in locals() else source_node).nodeid),
            message=message,
            severity=severity,
            category=category,
        )


    async def start(self):
        async def _serve():
            async with self.server:
                await asyncio.gather(
                    self._mqtt_loop(),
                    self._heartbeat_task(self.server.nodes.objects),
                )

        try:
            await _serve()
        except OSError as e:
            if getattr(e, "errno", None) != 98:  # 98 = address already in use
                raise

            # Porta ocupada: tenta portas seguintes
            host, port, path = self.endpoint.replace("opc.tcp://", "").partition("/")[0].partition(":")[::2] + ("/" + self.endpoint.split("/", 3)[-1] if "/" in self.endpoint[10:] else "")
            try:
                port = int(port)  # type: ignore[assignment]
            except Exception:
                port = 4840

            base_host = "0.0.0.0"  # bind all interfaces
            for new_port in range(port + 1, port + 6):
                new_ep = f"opc.tcp://{base_host}:{new_port}{path if isinstance(path, str) else ''}"
                logger.warning("Porta %s ocupada. Tentando %s ...", port, new_ep)
                self.server.set_endpoint(new_ep)
                self.endpoint = new_ep
                try:
                    await _serve()
                    return
                except OSError as e2:
                    if getattr(e2, "errno", None) == 98:
                        continue
                    raise
            raise  # nenhuma porta disponível


    async def _heartbeat_task(self, source_node):
        # Emite evento informativo periódico para ver atividade
        while True:
            await self.fire_event(source_node, "status", "heartbeat", SEVERITY["INFO"])
            await asyncio.sleep(30)


    # MQTT

    async def _mqtt_loop(self):
        client = MQTTClient(self.mqtt_client_id)

        if self.mqtt_username and self.mqtt_password:
            client.set_auth_credentials(self.mqtt_username, self.mqtt_password)

        def on_connect(c, flags, rc, properties):  # noqa: ANN001
            logger.info("MQTT conectado: {}:{}, rc={} flags={}", self.mqtt_host, self.mqtt_port, rc, flags)
            c.subscribe(TOPIC_ELEC)
            c.subscribe(TOPIC_ENV)
            c.subscribe(TOPIC_VIB)

   
            c.subscribe("scgdi/sensor/electrical")
            c.subscribe("scgdi/sensor/environment")
            c.subscribe("scgdi/sensor/vibration")

      
            c.subscribe("scgdi/sensor/energia")
            c.subscribe("scgdi/sensor/ambiente")
            c.subscribe("scgdi/sensor/vibracao")

        async def on_message(c, topic, payload, qos, properties):  # noqa: ANN001
            if topic.startswith("$SYS/"):
                return
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning("MQTT payload inválido em {}", topic)
                return

            if topic in (TOPIC_ELEC, "scgdi/sensor/electrical"):
                data = _normalize_electrical_payload(data)
                await self._handle_electrical(ElectricalPayload(**data))
            elif topic in (TOPIC_ENV, "scgdi/sensor/environment"):
                data = _normalize_environment_payload(data)
                await self._handle_environment(EnvironmentPayload(**data))
            elif topic in (TOPIC_VIB, "scgdi/sensor/vibration"):
                data = _normalize_vibration_payload(data)
                await self._handle_vibration(VibrationPayload(**data))
            elif topic == "scgdi/sensor/energia":
                data = _normalize_electrical_payload(data)  
                await self._handle_electrical(ElectricalPayload(**data))
            elif topic == "scgdi/sensor/ambiente":
                data = _normalize_environment_payload(data)
                await self._handle_environment(EnvironmentPayload(**data))
            elif topic == "scgdi/sensor/vibracao":
                data = _normalize_vibration_payload(data)
                await self._handle_vibration(VibrationPayload(**data))

        client.on_connect = on_connect
        client.on_message = on_message

        self.mqtt = client
        await client.connect(self.mqtt_host, self.mqtt_port, keepalive=60, ssl=None)

        try:
           #  client.subscribe("$SYS/#")  # debug
            while True:
                await asyncio.sleep(1)
        finally:
            await client.disconnect()

  
    # Handlers de atualização de variáveis + regras de eventos/alarmes
    

    async def _set_and_store(self, name: str, ts: str, value: float, extra: Dict | None = None):
        node = self.vars[name]
        await node.write_value(value)
        path = (
            f"{MOTOR_NODE_NAME}."
            + (
                "Electrical."
                if name
                in {
                    "VoltageA",
                    "VoltageB",
                    "VoltageC",
                    "CurrentA",
                    "CurrentB",
                    "CurrentC",
                    "PowerActive",
                    "PowerReactive",
                    "PowerApparent",
                    "EnergyActive",
                    "EnergyReactive",
                    "EnergyApparent",
                    "PowerFactor",
                    "Frequency",
                }
                else "Environment."
                if name in {"Temperature", "Humidity", "CaseTemperature"}
                else "Vibration."
            )
            + name
        )
        await self.storage.add_var(ts, path, value, extra)

    async def _handle_electrical(self, p: ElectricalPayload):
        ts = p.timestamp
        # Atualiza variáveis
        await self._set_and_store("VoltageA", ts, p.voltage.get("a", 0.0))
        await self._set_and_store("VoltageB", ts, p.voltage.get("b", 0.0))
        await self._set_and_store("VoltageC", ts, p.voltage.get("c", 0.0))
        await self._set_and_store("CurrentA", ts, p.current.get("a", 0.0))
        await self._set_and_store("CurrentB", ts, p.current.get("b", 0.0))
        await self._set_and_store("CurrentC", ts, p.current.get("c", 0.0))
        await self._set_and_store("PowerActive", ts, p.power.get("active", 0.0))
        await self._set_and_store("PowerReactive", ts, p.power.get("reactive", 0.0))
        await self._set_and_store("PowerApparent", ts, p.power.get("apparent", 0.0))
        await self._set_and_store("EnergyActive", ts, p.energy.get("active", 0.0))
        await self._set_and_store("EnergyReactive", ts, p.energy.get("reactive", 0.0))
        await self._set_and_store("EnergyApparent", ts, p.energy.get("apparent", 0.0))
        await self._set_and_store("PowerFactor", ts, p.powerFactor)
        await self._set_and_store("Frequency", ts, p.frequency)

        # Regras de alarme: tensão ±10%
        for phase_name, v in {
            "VoltageA": p.voltage.get("a", 0.0),
            "VoltageB": p.voltage.get("b", 0.0),
            "VoltageC": p.voltage.get("c", 0.0),
        }.items():
            dev = pct_over(v, NOMINAL_VOLTAGE)
            src = self.vars[phase_name]
            if dev > OVER_UNDER_TOL:
                await self.fire_event(src, "Electrical", "Overvoltage detected", SEVERITY["HIGH"])
            elif dev < -OVER_UNDER_TOL:
                await self.fire_event(src, "Electrical", "Undervoltage detected", SEVERITY["HIGH"])

        # Corrente > 10% acima nominal
        for phase_name, i in {
            "CurrentA": p.current.get("a", 0.0),
            "CurrentB": p.current.get("b", 0.0),
            "CurrentC": p.current.get("c", 0.0),
        }.items():
            src = self.vars[phase_name]
            if pct_over(i, NOMINAL_CURRENT) > OVER_UNDER_TOL:
                await self.fire_event(src, "Electrical", "Overcurrent detected", SEVERITY["HIGH"])

    async def _handle_environment(self, p: EnvironmentPayload):
        ts = p.timestamp
        await self._set_and_store("Temperature", ts, p.temperature)
        await self._set_and_store("Humidity", ts, p.humidity)
        await self._set_and_store("CaseTemperature", ts, p.caseTemperature)

        # Alarme crítico: caseTemperature > 60°C
        if p.caseTemperature > CASE_TEMP_CRIT:
            await self.fire_event(self.vars["CaseTemperature"], "Environment", "Case temperature critical", SEVERITY["CRIT"])

    async def _handle_vibration(self, p: VibrationPayload):
        ts = p.timestamp
        await self._set_and_store("Axial", ts, p.axial)
        await self._set_and_store("Radial", ts, p.radial)
        if max(p.axial, p.radial) > 0.2:
            await self.fire_event(self.vars["Axial"], "Vibration", "Slight vibration increase", SEVERITY["LOW"])



# Entry point

async def main():
    try:
        import uvloop  # type: ignore
        uvloop.install()
    except Exception:  # noqa: BLE001
        pass

    app = MotorOPCUAServer()

    # Tenta liberar a porta do endpoint
    _, port, _ = split_endpoint(app.endpoint)
    if free_port(port, name_hint="src.server"):
        logger.info("Porta %s liberada (ou já estava livre).", port)
    else:
        logger.warning("Não consegui liberar a porta %s (talvez permissão). Vou tentar iniciar assim mesmo.", port)

    await app.init()
    logger.info("OPC UA endpoint: {}", app.endpoint)
    logger.info("MQTT broker: {}:{}", app.mqtt_host, app.mqtt_port)
    await app.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print()
        logger.info("Encerrado pelo usuário.")

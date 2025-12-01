from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, Optional


class ElectricalPayload(BaseModel):
    timestamp: str
    voltage: Dict[str, float]
    current: Dict[str, float]
    power: Dict[str, float]
    energy: Dict[str, float]
    powerFactor: float
    frequency: float

class EnvironmentPayload(BaseModel):
    timestamp: str
    temperature: float
    humidity: float
    caseTemperature: float

class VibrationPayload(BaseModel):
    timestamp: str
    axial: float
    radial: float

SEVERITY = {
    "INFO": 100,
    "LOW": 250,
    "MED": 500,
    "HIGH": 700,
    "CRIT": 900,
}

NOMINAL_VOLTAGE = 220.0 
NOMINAL_CURRENT = 10.0   

# Limites para alarmes
OVER_UNDER_TOL = 0.10  
CASE_TEMP_CRIT = 60.0 

# Nomes de tópicos
TOPIC_ELEC = "scgdi/motor/electrical"
TOPIC_ENV = "scgdi/motor/environment"
TOPIC_VIB = "scgdi/motor/vibration"

# Estrutura dos nós/variáveis do servidor
MOTOR_NODE_NAME = "Motor50CV"
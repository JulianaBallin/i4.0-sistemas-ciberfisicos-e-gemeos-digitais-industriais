# Checklist – Exercício Final SCGDI

## Resumo
Checklist dos requisitos do arquivo **scgdi/exercicio_final.md**

### Legenda
- **OK** = Atende completamente
- **PARCIAL** = Atende em parte / requer ajuste
- **FALTA** = Falta implementar

## Checklist de requisitos

| Requisito | Status | Onde | Observações |
|---|---|---|---|
| Servidor OPC UA com árvore e variáveis conforme estrutura | OK | src/server.py → init() cria Motor50CV/Electrical/Environment/Vibration e variáveis | Estrutura alinhada ao enunciado; variáveis por fase e grupos. |
| Regras de geração de eventos e alarmes | OK | src/server.py → handlers e _prepare_event_type() | ±10% tensão, +10% corrente, temperatura carcaça >60°C; heartbeat INFO periódico. |
| Histórico de variáveis habilitado | OK | src/server.py → enable_history_data_change(...) | Histórico OPC UA e persistência em SQLite (src/storage.py). |
| Histórico de eventos habilitado | OK | src/server.py → enable_history_event(...) | Eventos persistidos em SQLite (event_history). |
| Nodeset personalizado | OK | src/server.py → _prepare_event_type() cria SCGDIEventType | Tipo de evento custom implementado.
| Integração com broker MQTT remoto (lse.dev.br) | OK (configurável) | src/server.py (cliente) / src/publisher.py (simulador) | Servidor usa host do .env (default localhost); publisher já aponta p/ lse.dev.br. Defina MQTT_HOST=lse.dev.br. |
| Tópicos e formato JSON | OK | src/model.py (TOPIC_* e modelos); src/server.py normalizadores; src/publisher.py geradores | Os três tópicos estão cobertos; modelos são compatíveis. |

## Cobertura da árvore de nós
**Electrical** — Status: OK

- Variáveis encontradas: `VoltageA, VoltageB, VoltageC, CurrentA, CurrentB, CurrentC, PowerActive, PowerReactive, PowerApparent, EnergyActive, EnergyReactive, EnergyApparent, PowerFactor, Frequency`

**Environment** — Status: OK

- Variáveis encontradas: `Temperature, Humidity, CaseTemperature`

**Vibration** — Status: OK

- Variáveis encontradas: `Axial, Radial`


## Tópicos MQTT e formatos
- Esperados: `scgdi/motor/electrical`, `scgdi/motor/environment`, `scgdi/motor/vibration`
- Implementados: `TOPIC_ELEC`, `TOPIC_ENV`, `TOPIC_VIB` em `src/model.py`
- `src/server.py` assina e normaliza payloads; `src/publisher.py` publica payloads sintéticos compatíveis.

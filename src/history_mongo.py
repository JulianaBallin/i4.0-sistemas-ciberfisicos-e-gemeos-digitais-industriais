
from __future__ import annotations

from typing import Any, List, Optional
from datetime import datetime, timezone

try:
    from asyncua.server.history import HistoryStorageInterface  # type: ignore
except Exception:  # pragma: no cover
    HistoryStorageInterface = object  # type: ignore[misc,assignment]

class HistoryMongoDB(HistoryStorageInterface):  # type: ignore[misc]
    """
    Stub de armazenamento de histórico para OPC UA.
    Este stub não persiste nada; serve apenas para manter compatibilidade
    caso algum módulo importe HistoryMongoDB.
    """
    def __init__(self, server: Any) -> None:
        self.server = server


    async def initialize(self) -> None:
        return

    async def add_node_value(self, node: Any, datavalue: Any) -> None:
        return

    async def read_node_history(
        self,
        node: Any,
        start: Optional[datetime],
        end: Optional[datetime],
        num_values: int = 0,
        cont: Any = None,
    ):
        # Retorna lista vazia (sem histórico via OPC UA)
        return []

    async def read_event_history(
        self,
        source: Any,
        start: Optional[datetime],
        end: Optional[datetime],
        num_events: int = 0,
        cont: Any = None,
    ):
        # Retorna lista vazia (sem histórico de eventos via OPC UA)
        return []

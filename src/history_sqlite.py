
from __future__ import annotations
from typing import Any, Optional, List, Tuple
from datetime import datetime
import aiosqlite
from asyncua import ua
try:
    from asyncua.server.history import HistoryStorageInterface  # type: ignore
except Exception:
    HistoryStorageInterface = object 

class HistorySQLite(HistoryStorageInterface):  
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def read_node_history(
        self,
        node: Any,
        start: Optional[datetime],
        end: Optional[datetime],
        num_values: int = 0,
        cont: Any = None,
    ) -> List[ua.DataValue]:
        """
        Retorna DataValues para suportar HistoryRead(Data).
        Mapeia pelo caminho 'path' que você salva no SQLite.
        """
        browse_name = await node.read_browse_name()
        path = browse_name.Name

        query = """
            SELECT ts, value
            FROM var_history
            WHERE path LIKE ? AND (? IS NULL OR ts >= ?) AND (? IS NULL OR ts <= ?)
            ORDER BY ts ASC
        """
        params = (f"%{path}", start.isoformat() if start else None, start.isoformat() if start else None,
                  end.isoformat() if end else None, end.isoformat() if end else None)

        out: List[ua.DataValue] = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cur:
                async for ts, value in cur:
                    dv = ua.DataValue(ua.Variant(value, ua.VariantType.Double))
                    dv.SourceTimestamp = datetime.fromisoformat(ts)
                    out.append(dv)
                    if num_values and len(out) >= num_values:
                        break
        return out

    async def read_event_history(
        self,
        source: Any,
        start: Optional[datetime],
        end: Optional[datetime],
        num_events: int = 0,
        cont: Any = None,
    ):
        """
        Opcional: para HistoryRead(Event). Se quiser, retorne tuplas/structures
        coerentes com o tipo de evento que você disparou (BaseEventType ou custom).
        Por simplicidade, pode retornar lista vazia inicialmente e evoluir depois.
        """
        return []

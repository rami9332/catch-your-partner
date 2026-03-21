from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List


EventHandler = Callable[[dict], None]


@dataclass
class EventRecord:
    name: str
    payload: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._records: List[EventRecord] = []

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        record = EventRecord(name=event_name, payload=payload)
        self._records.append(record)

        for handler in self._handlers.get(event_name, []):
            try:
                handler(payload)
            except Exception:
                # Module listeners must never block the core flow.
                continue

    def recent(self, limit: int = 25) -> List[dict]:
        return [
            {
                "name": record.name,
                "payload": record.payload,
                "created_at": record.created_at,
            }
            for record in self._records[-limit:]
        ]

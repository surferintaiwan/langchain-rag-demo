from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel


class AuditEntry(BaseModel):
    timestamp: str
    question: str
    route: str
    has_retrieval: bool
    response_type: str


def create_audit_entry(
    question: str,
    route: str,
    has_retrieval: bool,
    response_type: str,
) -> AuditEntry:
    return AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        question=question,
        route=route,
        has_retrieval=has_retrieval,
        response_type=response_type,
    )


def append_audit_log(logs: List[AuditEntry], entry: AuditEntry) -> List[AuditEntry]:
    logs.insert(0, entry)
    return logs

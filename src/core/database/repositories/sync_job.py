"""Sync job repository — tenant-scoped access to background sync jobs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database.models import SyncJob


class SyncJobRepository:
    """Tenant-scoped read access for SyncJob models."""

    def __init__(self, session: Session, tenant_id: str) -> None:
        self._session = session
        self._tenant_id = tenant_id

    def get_running_by_type(self, sync_type: str) -> SyncJob | None:
        """Return the active sync job for the given type, if one exists."""
        stmt = select(SyncJob).where(
            SyncJob.tenant_id == self._tenant_id,
            SyncJob.status == "running",
            SyncJob.sync_type == sync_type,
        )
        return self._session.scalars(stmt).first()

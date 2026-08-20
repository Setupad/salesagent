"""Repository for first-party MCP OAuth clients."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database.models import OAuthAuthorizationCode, OAuthClient
from src.core.oauth_service import DEFAULT_MCP_OAUTH_SCOPE, OAuthClientCredentials


class OAuthClientRepository:
    """Data access for OAuth clients tied to advertiser principals."""

    def __init__(self, session: Session):
        self.session = session

    def get_active_client(
        self,
        *,
        tenant_id: str,
        client_id: str,
        principal_id: str | None = None,
    ) -> OAuthClient | None:
        stmt = select(OAuthClient).filter_by(tenant_id=tenant_id, client_id=client_id, is_active=True)
        if principal_id is not None:
            stmt = stmt.filter_by(principal_id=principal_id)
        return self.session.scalars(stmt).first()

    def get_active_client_by_client_id(self, client_id: str) -> OAuthClient | None:
        stmt = select(OAuthClient).filter_by(client_id=client_id, is_active=True)
        return self.session.scalars(stmt).first()

    def get_active_client_by_principal(self, *, tenant_id: str, principal_id: str) -> OAuthClient | None:
        stmt = select(OAuthClient).filter_by(tenant_id=tenant_id, principal_id=principal_id, is_active=True)
        return self.session.scalars(stmt).first()

    def create_for_principal(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        credentials: OAuthClientCredentials,
        scopes: list[str] | None = None,
        redirect_uris: list[str] | None = None,
        created_at: datetime | None = None,
    ) -> OAuthClient:
        timestamp = created_at or datetime.now(UTC)
        oauth_client = OAuthClient(
            tenant_id=tenant_id,
            principal_id=principal_id,
            client_id=credentials.client_id,
            client_secret_hash=credentials.client_secret_hash,
            scopes=scopes or [DEFAULT_MCP_OAUTH_SCOPE],
            redirect_uris=redirect_uris or [],
            is_active=True,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.session.add(oauth_client)
        return oauth_client

    def create_authorization_code(
        self,
        *,
        code_hash: str,
        tenant_id: str,
        client_id: str,
        principal_id: str,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scopes: list[str],
        resource: str,
        expires_at: datetime,
        created_at: datetime | None = None,
    ) -> OAuthAuthorizationCode:
        timestamp = created_at or datetime.now(UTC)
        authorization_code = OAuthAuthorizationCode(
            code_hash=code_hash,
            tenant_id=tenant_id,
            client_id=client_id,
            principal_id=principal_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scopes=scopes,
            resource=resource,
            expires_at=expires_at,
            created_at=timestamp,
        )
        self.session.add(authorization_code)
        return authorization_code

    def get_authorization_code(self, code_hash: str) -> OAuthAuthorizationCode | None:
        stmt = select(OAuthAuthorizationCode).filter_by(code_hash=code_hash)
        return self.session.scalars(stmt).first()

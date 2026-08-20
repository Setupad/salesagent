import base64
import hashlib
from datetime import UTC, datetime

import pytest

from src.core.oauth_service import (
    OAuthTokenValidationError,
    generate_oauth_client_credentials,
    hash_authorization_code,
    issue_mcp_access_token,
    validate_mcp_access_token,
    verify_client_secret,
    verify_pkce_s256,
)


def test_generate_oauth_client_credentials_returns_one_time_secret_and_hash():
    credentials = generate_oauth_client_credentials()

    assert credentials.client_id.startswith("mcp_client_")
    assert credentials.client_secret.startswith("mcp_secret_")
    assert credentials.client_secret_hash != credentials.client_secret
    assert verify_client_secret(credentials.client_secret, credentials.client_secret_hash)
    assert not verify_client_secret("mcp_secret_wrong", credentials.client_secret_hash)


def test_issue_and_validate_mcp_access_token_returns_principal_claims():
    token = issue_mcp_access_token(
        tenant_id="tenant_123",
        principal_id="principal_456",
        client_id="mcp_client_abc",
        issuer="https://agent.example.com",
        audience="https://agent.example.com/mcp",
        scopes=["mcp:principal"],
        now=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    )

    claims = validate_mcp_access_token(
        token,
        issuer="https://agent.example.com",
        audience="https://agent.example.com/mcp",
        now=datetime(2026, 8, 19, 12, 1, tzinfo=UTC),
    )

    assert claims.tenant_id == "tenant_123"
    assert claims.principal_id == "principal_456"
    assert claims.client_id == "mcp_client_abc"
    assert claims.scopes == ["mcp:principal"]
    assert claims.subject == "principal_456"


def test_validate_mcp_access_token_rejects_wrong_audience():
    token = issue_mcp_access_token(
        tenant_id="tenant_123",
        principal_id="principal_456",
        client_id="mcp_client_abc",
        issuer="https://agent.example.com",
        audience="https://agent.example.com/mcp",
        scopes=["mcp:principal"],
        now=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(OAuthTokenValidationError):
        validate_mcp_access_token(
            token,
            issuer="https://agent.example.com",
            audience="https://other.example.com/mcp",
            now=datetime(2026, 8, 19, 12, 1, tzinfo=UTC),
        )


def test_authorization_code_hash_is_stable_and_not_plaintext():
    code = "mcp_code_test"

    digest = hash_authorization_code(code)

    assert digest == hashlib.sha256(code.encode("utf-8")).hexdigest()
    assert digest != code


def test_verify_pkce_s256_accepts_matching_verifier_and_rejects_wrong_value():
    verifier = "verifier-for-remote-mcp-client"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")

    assert verify_pkce_s256(verifier, challenge) is True
    assert verify_pkce_s256("wrong-verifier", challenge) is False


def test_validate_mcp_access_token_rejects_expired_token():
    token = issue_mcp_access_token(
        tenant_id="tenant_123",
        principal_id="principal_456",
        client_id="mcp_client_abc",
        issuer="https://agent.example.com",
        audience="https://agent.example.com/mcp",
        scopes=["mcp:principal"],
        now=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
        lifetime_seconds=60,
    )

    with pytest.raises(OAuthTokenValidationError):
        validate_mcp_access_token(
            token,
            issuer="https://agent.example.com",
            audience="https://agent.example.com/mcp",
            now=datetime(2026, 8, 19, 12, 2, tzinfo=UTC),
        )

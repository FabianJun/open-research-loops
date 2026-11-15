import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import parse_qs, urlparse

import pytest

from research_loops.openai_auth import ChatGPTAuth, TokenStore, AuthError, ISSUER, TOKEN, RESOURCE, SCOPES


@pytest.fixture
def oauth(tmp_path):
    jwt = pytest.importorskip("jwt")
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "offline-key"
    class Endpoint:
        requests = None
        claims = None
        scope = SCOPES
        rotation = 0
        def __init__(self):
            self.requests = []
        def __call__(self, method, url, *, headers=None, data=None):
            self.requests.append((method, url, headers, data))
            if url.endswith("jwks.json"):
                return {"keys": [jwk]}
            if url == TOKEN:
                fields = parse_qs(data.decode())
                assert fields["resource"] == [RESOURCE] and "client_secret" not in fields
                assert fields["client_id"] == ["oaiapp_offline"]
                if fields["grant_type"] == ["refresh_token"]:
                    self.rotation += 1
                    assert fields["refresh_token"] == [f"refresh-{self.rotation - 1}"]
                    assert "scope" not in fields
                return dict(access_token=f"access-{self.rotation}", refresh_token=f"refresh-{self.rotation}",
                    id_token=jwt.encode(self.claims, key, algorithm="RS256", headers={"kid": "offline-key"}),
                    token_type="Bearer", expires_in=3600, earliest_refresh_at=0, scope=self.scope)
            assert url == RESOURCE + "/models"
            assert headers["Authorization"] == f"Bearer access-{self.rotation}"
            return {"models": [{"slug": "hidden", "visibility": "hide", "display_name": "Hidden"},
                {"slug": "gpt-6-astra", "visibility": "list", "display_name": "GPT-6 Astra"}]}
    endpoint = Endpoint()
    auth = ChatGPTAuth(TokenStore(tmp_path / "user-auth"), request=endpoint)
    pending = auth.begin("http://127.0.0.1:1455/auth/callback")
    endpoint.claims = dict(iss=ISSUER, aud="oaiapp_offline", sub="offline-subject", nonce=pending.nonce,
        iat=int(time.time()), exp=int(time.time()) + 3600)
    return auth, pending, endpoint


def complete(auth, pending):
    return auth.complete(pending, dict(state=pending.state, code="offline-code", client_id="oaiapp_offline"))


def test_dynamic_registration_pkce_and_safe_storage(oauth):
    auth, pending, endpoint = oauth
    query = parse_qs(urlparse(pending.url()).query)
    assert query["client_id"] == ["dynamic_agent_client"]
    assert query["agent_name_hint"] == ["open-research-loops"]
    assert query["ext_agent_host_id"][0].startswith("urn:uuid:")
    assert query["code_challenge"] == [base64.urlsafe_b64encode(hashlib.sha256(pending.verifier.encode()).digest()).decode().rstrip("=")]
    assert set(query["scope"][0].split()) == set(SCOPES.split())
    label = complete(auth, pending)
    assert auth.store.accounts() == [(label, True)]
    assert auth.models() == [{"slug": "gpt-6-astra", "display_name": "GPT-6 Astra"}]
    exchange = parse_qs(endpoint.requests[0][3].decode())
    assert exchange["redirect_uri"] == [pending.redirect_uri]
    assert exchange["code_verifier"] == [pending.verifier]
    assert exchange["client_id"] == ["oaiapp_offline"]
    if os.name != "nt":
        assert auth.store.path.stat().st_mode & 0o777 == 0o600
        assert auth.store.root.stat().st_mode & 0o777 == 0o700
    else:
        import subprocess
        acl = subprocess.run(["icacls", str(auth.store.path)], capture_output=True, check=True, text=True).stdout
        assert "S-1-1-0" not in acl and "BUILTIN\\Users" not in acl
    returning = auth.begin("http://127.0.0.1:54321/auth/callback", label)
    values = parse_qs(urlparse(returning.url()).query)
    assert values["client_id"] == ["oaiapp_offline"]
    assert "agent_name_hint" not in values and "id_token_hint" in values
    assert returning.host_id == pending.host_id and returning.state != pending.state and returning.nonce != pending.nonce
    with pytest.raises(AuthError, match="consumed"):
        complete(auth, pending)


@pytest.mark.parametrize("changes", [{"state": "wrong"}, {"error": "access_denied"}, {"client_id": "dynamic_agent_client"}, {"client_id": ""}, {"code": ""}])
def test_callback_refusals_precede_exchange(oauth, changes):
    auth, pending, endpoint = oauth
    with pytest.raises(AuthError):
        auth.complete(pending, {"state": pending.state, "code": "fake", "client_id": "oaiapp_offline", **changes})
    assert not endpoint.requests


@pytest.mark.parametrize("changes", [{"iss": "https://evil.invalid"}, {"aud": "different-client"}, {"exp": 1}, {"nonce": "wrong"}, {"sub": ""}])
def test_id_token_claims_fail_closed(oauth, changes):
    auth, pending, endpoint = oauth
    endpoint.claims.update(changes)
    with pytest.raises(AuthError, match="ID token"):
        complete(auth, pending)
    assert auth.store.accounts() == []


def test_invalid_signature_and_returning_identity(oauth):
    auth, pending, endpoint = oauth
    label = complete(auth, pending)
    returning = auth.begin("http://127.0.0.1:1455/auth/callback", label)
    endpoint.claims.update(nonce=returning.nonce, sub="different-identity")
    with pytest.raises(AuthError, match="identity mismatch"):
        complete(auth, returning)
    assert auth.store.accounts() == [(label, True)]
    from cryptography.hazmat.primitives.asymmetric import rsa
    import jwt
    evil = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encoded = jwt.encode(endpoint.claims, evil, algorithm="RS256", headers={"kid": "offline-key"})
    with pytest.raises(AuthError, match="ID token"):
        auth.identity(encoded, "oaiapp_offline", returning.nonce)


def test_rotating_refresh_serialized_across_clients(oauth):
    auth, pending, endpoint = oauth
    complete(auth, pending)
    first = auth.store.read()
    expires = first["accounts"][first["active"]]["expires_at"]
    auth.clock = lambda: expires - 30
    other = ChatGPTAuth(TokenStore(auth.store.root), request=endpoint, clock=auth.clock)
    with ThreadPoolExecutor(2) as pool:
        tokens = list(pool.map(lambda client: client.access_token(), [auth, other]))
    assert tokens == ["access-1", "access-1"] and endpoint.rotation == 1
    saved = auth.store.read()["accounts"][first["active"]]
    assert saved["refresh_token"] == "refresh-1" and saved["access_token"] == "access-1"
    assert saved["expires_at"] == expires - 30 + 3600


def test_missing_permission_and_no_key_fallback(oauth):
    auth, pending, endpoint = oauth
    with pytest.raises(AuthError, match="no API-key fallback"):
        auth.access_token()
    endpoint.scope = "openid profile email"
    complete(auth, pending)
    with pytest.raises(AuthError, match="plan usage not authorized"):
        auth.models()
    assert not any(url.endswith("/models") for _, url, _, _ in endpoint.requests)


def test_storage_refuses_repository_and_symlink(tmp_path):
    with pytest.raises(AuthError, match="outside"):
        TokenStore(Path.cwd() / ".bad-tokens")
    with pytest.raises(AuthError, match="outside"):
        TokenStore(tmp_path / "project" / "tokens", project=tmp_path / "project")


def test_expired_refresh_has_no_automatic_reauthentication(oauth):
    auth, pending, endpoint = oauth
    label = complete(auth, pending)
    auth.clock = lambda: time.time() + 4000
    def expired(*args, **kwargs):
        raise AuthError("OpenAI auth HTTP 400: invalid_grant; no fallback")
    auth.request = expired
    with pytest.raises(AuthError, match="invalid_grant"):
        auth.access_token()
    record = auth.store.read()["accounts"][label]
    assert "access_token" not in record and record["client_id"] == "oaiapp_offline"


def test_sign_in_listener_precedes_browser_and_validates_callback(oauth):
    from research_loops.openai_auth import login
    from io import BytesIO
    from urllib.parse import urlencode
    auth, _, endpoint = oauth
    state = {}
    class Listener:
        server_port = 1455
        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            self.handler = handler
            state["listening"] = True
        def __enter__(self):
            return self
        def __exit__(self, *args):
            state["closed"] = True
        def handle_request(self):
            handler = self.handler.__new__(self.handler)
            handler.path = "/auth/callback?" + urlencode(dict(state=state["query"]["state"][0], code="stub-code", client_id="oaiapp_offline"))
            handler.send_response = lambda code: state.update(status=code)
            handler.end_headers = lambda: None
            handler.wfile = BytesIO()
            handler.do_GET()
    def browser(url):
        assert state["listening"] and "closed" not in state
        state["query"] = parse_qs(urlparse(url).query)
        endpoint.claims["nonce"] = state["query"]["nonce"][0]
        return True
    label = login(auth, browser=browser, server_factory=Listener)
    assert state["closed"] and state["status"] == 200
    assert auth.store.accounts() == [(label, True)]


def test_refresh_waits_for_server_earliest_time(oauth):
    auth, pending, endpoint = oauth
    label = complete(auth, pending)
    with auth.store.locked():
        value = auth.store.read()
        expiry = value["accounts"][label]["expires_at"]
        value["accounts"][label]["earliest_refresh_at"] = expiry - 10
        auth.store.write(value)
    auth.clock = lambda: expiry - 30
    assert auth.access_token() == "access-0" and endpoint.rotation == 0
    auth.clock = lambda: expiry - 5
    assert auth.access_token() == "access-1" and endpoint.rotation == 1

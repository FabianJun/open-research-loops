"""Sign in with ChatGPT public-client OAuth. No credential access on import.

Only explicitly invoked login/model/worker operations call the transport. Tests
inject a stub; no environment credential or other app's credential file is used.
"""

import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request
from urllib.error import HTTPError, URLError
import uuid

from research_loops.domain import IntegrityError
from research_loops.locking import ProjectLock

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"


class AuthError(IntegrityError):
    pass


def request_json(method, url, *, headers=None, data=None):
    """No redirects, error bodies or request headers enter diagnostics."""
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with build_opener(NoRedirect).open(Request(url, data=data, headers=headers or {}, method=method), timeout=30) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise AuthError("oversized authentication response")
            return json.loads(raw)
    except HTTPError as exc:
        # Only allow known machine codes into exceptions, never arbitrary bodies.
        code = "request_failed"
        try:
            value = json.loads(exc.read(10000))
            candidate = value.get("error")
            if isinstance(candidate, dict):
                candidate = candidate.get("code")
            if candidate in {"invalid_grant", "invalid_refresh_token", "token_expired", "refresh_token_expired",
                    "refresh_token_invalidated", "refresh_token_reused", "invalid_client"}:
                code = candidate
        except (ValueError, TypeError, AttributeError):
            pass
        raise AuthError(f"OpenAI auth HTTP {exc.code}: {code}; no fallback") from None
    except (URLError, ValueError, OSError):
        raise AuthError("OpenAI authentication transport failed; no fallback") from None


def default_root():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "research-loops" / "auth"


def private_directory(path):
    if path.is_symlink():
        raise AuthError("auth storage must not be a symlink")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "nt":
        # Apply owner-only DACL before writing any secret. No shell interpolation.
        import csv
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, check=True, text=True)
        sid = next(csv.reader([identity.stdout.strip()]))[1]
        # Replace the whole DACL, including any explicit grants on an older dir.
        import ctypes
        from ctypes import wintypes
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        descriptor = ctypes.c_void_p()
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(f"D:P(A;OICI;FA;;;{sid})", 1, ctypes.byref(descriptor), None):
            raise AuthError("cannot establish private Windows auth storage")
        try:
            if not advapi.SetFileSecurityW(str(path), 0x80000004, descriptor):
                raise AuthError("cannot establish private Windows auth storage")
        finally:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LocalFree.argtypes = [ctypes.c_void_p]
            kernel.LocalFree(descriptor)
    else:
        path.chmod(0o700)
        if path.stat().st_uid != os.getuid():
            raise AuthError("auth storage owner mismatch")


_threads = threading.Lock()


class TokenStore:
    def __init__(self, root=None, *, project=None):
        self.root = Path(root) if root is not None else default_root()
        self.root = self.root.absolute()
        # Never keep tokens in this source checkout or the scientist's project.
        forbidden = [Path(__file__).resolve().parents[2]]
        if project is not None:
            forbidden.append(Path(project).resolve())
        if any(self.root.resolve().is_relative_to(path) for path in forbidden):
            raise AuthError("token storage must be outside the repository/project")
        self.path = self.root / "openai.json"

    @contextmanager
    def locked(self):
        with _threads:
            private_directory(self.root)
            deadline = time.monotonic() + 35
            while True:
                lock = ProjectLock(self.root)
                try:
                    lock.__enter__()
                    break
                except IntegrityError:
                    if time.monotonic() >= deadline:
                        raise AuthError("another process is refreshing credentials") from None
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock.__exit__()

    def read(self):
        if not self.path.exists():
            return {"host_id": "urn:uuid:" + str(uuid.uuid4()), "accounts": {}, "active": None}
        if self.path.is_symlink():
            raise AuthError("auth file must not be a symlink")
        if os.name != "nt" and (self.path.stat().st_mode & 0o077 or self.path.stat().st_uid != os.getuid()):
            raise AuthError("auth file permissions must be owner-only")
        try:
            return json.loads(self.path.read_bytes())
        except (ValueError, OSError):
            raise AuthError("invalid protected auth storage") from None

    def write(self, value):
        descriptor, name = tempfile.mkstemp(prefix=".tokens-", dir=self.root)
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            Path(name).unlink(missing_ok=True)

    def accounts(self):
        with self.locked():
            value = self.read()
            return [(label, label == value["active"]) for label in value["accounts"]]

    def select(self, label):
        with self.locked():
            value = self.read()
            if label not in value["accounts"]:
                raise AuthError("unknown account registration")
            value["active"] = label
            self.write(value)


@dataclass(repr=False)
class Pending:
    redirect_uri: str
    host_id: str
    state: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    nonce: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    verifier: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    client_id: str = "dynamic_agent_client"
    subject: str | None = None
    id_token: str | None = None
    consumed: bool = False

    def url(self):
        parsed = urlparse(self.redirect_uri)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path != "/auth/callback" or not parsed.port or parsed.query or parsed.fragment:
            raise AuthError("invalid loopback callback URI")
        values = dict(client_id=self.client_id, ext_agent_host_id=self.host_id,
            response_type="code", redirect_uri=self.redirect_uri, scope=SCOPES, resource=RESOURCE,
            state=self.state, nonce=self.nonce, code_challenge_method="S256",
            code_challenge=base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).decode().rstrip("="))
        if self.client_id == "dynamic_agent_client":
            values["agent_name_hint"] = "open-research-loops"
        elif self.id_token:
            values["id_token_hint"] = self.id_token
        return AUTHORIZE + "?" + urlencode(values)


class ChatGPTAuth:
    def __init__(self, store=None, request=request_json, clock=time.time):
        self.store = store or TokenStore()
        self.request, self.clock = request, clock

    def begin(self, redirect_uri, account=None):
        with self.store.locked():
            value = self.store.read()
            self.store.write(value)  # Persist stable host ID before the browser opens.
            selected = value["accounts"].get(account) if account else None
            if account and selected is None:
                raise AuthError("unknown account registration")
            return Pending(redirect_uri, value["host_id"], client_id=selected["client_id"] if selected else "dynamic_agent_client",
                subject=selected["subject"] if selected else None, id_token=selected.get("id_token") if selected else None)

    def post_token(self, values):
        return self.request("POST", TOKEN, headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=urlencode({**values, "resource": RESOURCE}).encode())

    def identity(self, encoded, client_id, nonce):
        import jwt
        try:
            header = jwt.get_unverified_header(encoded)
            keys = self.request("GET", ISSUER + "/.well-known/jwks.json")["keys"]
            key = next(key for key in keys if key.get("kid") == header.get("kid") and key.get("kty") == "RSA")
            claims = jwt.decode(encoded, jwt.PyJWK.from_dict(key).key, algorithms=["RS256"], audience=client_id,
                issuer=ISSUER, options={"require": ["sub", "exp", "iat", "nonce"]}, leeway=5)
            if not isinstance(claims["sub"], str) or not claims["sub"] or not hmac.compare_digest(claims["nonce"], nonce):
                raise ValueError()
            return claims["sub"]
        except (ValueError, TypeError, KeyError, StopIteration, jwt.PyJWTError):
            raise AuthError("ID token validation failed") from None

    def token_fields(self, response):
        try:
            if response["token_type"].lower() != "bearer" or not response["access_token"] or not response["refresh_token"]:
                raise ValueError()
            expires = int(response["expires_in"])
            if expires <= 0:
                raise ValueError()
            earliest = response.get("earliest_refresh_at", 0)
            if isinstance(earliest, str) and not earliest.replace(".", "", 1).isdigit():
                earliest = datetime.fromisoformat(earliest.replace("Z", "+00:00")).timestamp()
            return dict(access_token=response["access_token"], refresh_token=response["refresh_token"],
                scopes=response["scope"].split(), expires_at=self.clock() + expires,
                earliest_refresh_at=float(earliest), saved_at=self.clock())
        except (ValueError, KeyError, TypeError, AttributeError):
            raise AuthError("incomplete OAuth token response") from None

    def complete(self, pending, query):
        if pending.consumed:
            raise AuthError("authorization attempt already consumed")
        pending.consumed = True
        if not isinstance(query.get("state"), str) or not hmac.compare_digest(query["state"], pending.state):
            raise AuthError("OAuth state mismatch")
        if query.get("error"):
            raise AuthError("ChatGPT authorization declined or failed")
        client_id = query.get("client_id", pending.client_id)
        if not client_id.startswith("oaiapp_") or (pending.subject is not None and client_id != pending.client_id) or not query.get("code"):
            raise AuthError("missing or mismatched issued client ID/code")
        tokens = self.post_token(dict(grant_type="authorization_code", client_id=client_id,
            code=query["code"], code_verifier=pending.verifier, redirect_uri=pending.redirect_uri))
        subject = self.identity(tokens.get("id_token"), client_id, pending.nonce)
        if pending.subject is not None and subject != pending.subject:
            raise AuthError("returning account identity mismatch")
        fields = self.token_fields(tokens)
        label = hashlib.sha256((client_id + "\0" + subject).encode()).hexdigest()[:16]
        with self.store.locked():
            value = self.store.read()
            value["accounts"][label] = dict(client_id=client_id, subject=subject, id_token=tokens["id_token"], **fields)
            value["active"] = label
            self.store.write(value)
        return label  # Permission is checked before discovery/inference, even after valid sign-in.

    def access_token(self):
        with self.store.locked():
            value = self.store.read()
            account = value["accounts"].get(value["active"])
            if not account or not account.get("access_token"):
                raise AuthError("Sign in with ChatGPT required; no API-key fallback")
            if "chatgpt.tokens.use.direct" not in account["scopes"]:
                raise AuthError("ChatGPT plan usage not authorized; repeat sign-in or explicitly configure another mode")
            now = self.clock()
            if now >= account["expires_at"] - 60 and now >= account.get("earliest_refresh_at", 0):
                try:
                    response = self.post_token(dict(grant_type="refresh_token", client_id=account["client_id"], refresh_token=account["refresh_token"]))
                except AuthError as exc:
                    if any(code in str(exc) for code in ("invalid_grant", "invalid_refresh_token", "token_expired", "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused")):
                        for field_name in ("access_token", "refresh_token", "id_token"):
                            account.pop(field_name, None)
                        self.store.write(value)
                    raise
                account.update(self.token_fields(response))
                self.store.write(value)
            if now >= account["expires_at"]:
                raise AuthError("access token expired before permitted refresh; sign in again")
            if "chatgpt.tokens.use.direct" not in account["scopes"]:
                raise AuthError("refreshed grant does not permit ChatGPT plan usage")
            return account["access_token"]

    def models(self):
        data = self.request("GET", RESOURCE + "/models", headers={"Authorization": "Bearer " + self.access_token()})
        return [{"slug": item["slug"], "display_name": item["display_name"]} for item in data["models"] if item.get("visibility") == "list"]


def login(auth, *, account=None, browser=None, server_factory=None):
    """Invoked by the user later. Tests replace the listener/browser and HTTP seam."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import webbrowser
    callback = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Callback includes a code; never log it.
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path != "/auth/callback":
                self.send_error(404)
                return
            parsed_query = parse_qs(parsed.query, keep_blank_values=True)
            if any(len(values) != 1 for values in parsed_query.values()):
                self.send_error(400)
                return
            values = {key: values[0] for key, values in parsed_query.items()}
            if not hmac.compare_digest(values.get("state", ""), pending.state):
                self.send_error(400)
                return
            callback.update(values)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Return to research-loops to finish sign-in.")
    with (server_factory or HTTPServer)(("127.0.0.1", 0), Handler) as server:
        server.timeout = 1
        pending = auth.begin(f"http://127.0.0.1:{server.server_port}/auth/callback", account)
        if not (browser or webbrowser.open)(pending.url()):
            raise AuthError("cannot open system browser")
        deadline = time.monotonic() + 180
        while not callback and time.monotonic() < deadline:
            server.handle_request()
        if not callback:
            raise AuthError("sign-in callback timed out")
    return auth.complete(pending, callback)

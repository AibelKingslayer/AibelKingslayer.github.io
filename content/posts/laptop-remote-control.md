---
title: "Building a Laptop Remote Control with Flask, Tailscale, and HTTP Shortcuts"
description: "How I turned a small Python Flask script into a background Windows service controlled from an Android phone over Tailscale."
date: 2026-08-13T00:00:00+05:30
draft: false
tags:
  - Python
  - Flask
  - Tailscale
  - Windows
  - Security
  - Automation
---

I wanted a simple way to control a few functions on my Windows laptop from my phone: lock it, restart it, shut it down, update installed applications, clear temporary files, and open YouTube.

The first version was a tiny Flask server with one HTTP endpoint per action. It worked, but it also had several security and reliability problems. It stored an authentication token directly in the source code, executed commands through a shell, listened on every network interface, and performed an overly broad recursive deletion when clearing temporary files.

This post explains how I turned that prototype into a safer remote-control service that:

- is reachable only through Tailscale;
- accepts requests from one approved phone;
- authenticates every sensitive action with a bearer token;
- executes fixed commands without a shell;
- rate-limits requests and repeated actions;
- runs long tasks in the background;
- starts automatically when I sign in to Windows; and
- runs without leaving a terminal window open.

> This project is designed for personal devices inside a private Tailscale network. It should not be exposed directly to the public internet.

## The architecture

The final setup has three moving parts:

```text
Android phone
  └─ HTTP Shortcuts app
       └─ Encrypted Tailscale connection
            └─ Flask + Waitress on Windows
                 ├─ Lock workstation
                 ├─ Open YouTube
                 ├─ Run winget upgrades
                 ├─ Clear user temp files
                 ├─ Restart Windows
                 └─ Shut down Windows
```

Tailscale gives both devices stable private addresses and encrypts traffic between them. The Flask application binds specifically to the laptop's Tailscale address rather than `0.0.0.0`, which prevents it from listening on Wi-Fi, Ethernet, and other unrelated interfaces.

The HTTP Shortcuts app sends a `POST` request to a fixed endpoint. Each request includes an `Authorization: Bearer ...` header and is accepted only when the source address belongs to the allowlist.

## What was unsafe in the prototype?

The original proof of concept was intentionally small, but several patterns were unsuitable for a service capable of shutting down a computer.

### A secret embedded in source code

Hard-coding a token makes it easy to leak through screenshots, source-control history, backups, or copied snippets. Moving the token to a private environment file separates configuration from code and makes rotation much easier.

### Commands executed with `shell=True`

The first implementation passed command strings to a system shell. None of the endpoints accepted command input from the request, so immediate command injection was limited, but retaining a shell created unnecessary risk. A future edit that inserted user-controlled text could have turned it into a serious vulnerability.

The safer version uses fixed argument arrays and explicitly disables shell execution:

```python
subprocess.run(
    ["shutdown.exe", "/r", "/t", "5"],
    check=False,
    shell=False,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT,
    timeout=30,
)
```

No request parameter can change the executable or its arguments.

### Listening on every interface

This is convenient during development:

```python
app.run(host="0.0.0.0", port=5000)
```

It is also broader than necessary. The hardened service discovers or reads the laptop's Tailscale address and binds only to that address. It refuses a non-Tailscale address by default.

### Trusting a token without enough surrounding controls

A bearer token is useful, but it should not be the only boundary. The final service combines:

1. Tailscale network membership;
2. a source-IP allowlist;
3. bearer-token authentication;
4. constant-time token comparison;
5. request-rate limiting; and
6. per-action cooldowns.

This is defense in depth: a failure in one control does not immediately grant unrestricted access.

### Unsafe temporary-file deletion

A command such as `Remove-Item $env:TEMP\* -Recurse -Force` is compact, but destructive operations deserve explicit safeguards.

The replacement resolves the target directory, rejects filesystem roots and important system directories, avoids traversing links or Windows reparse points, and deletes only children of the validated temporary directory. Files currently in use are skipped instead of crashing the entire job.

## Secure configuration

Private settings live in `server.env`, which is excluded from source control:

```dotenv
REMOTE_CONTROL_TOKEN=replace-with-a-long-random-secret
REMOTE_CONTROL_ALLOWED_IPS=100.x.y.z
REMOTE_CONTROL_BIND_HOST=100.a.b.c
REMOTE_CONTROL_PORT=5000
REMOTE_CONTROL_REQUESTS_PER_MINUTE=30
```

The phone and laptop addresses above are placeholders. They should be replaced with the devices' actual Tailscale IPv4 addresses.

A strong token can be generated locally with Python:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The application refuses to start if the token is missing or too short. It also validates the IP addresses, port, and rate-limit configuration before creating the server.

## Authentication and request filtering

Every incoming request first passes through a shared protection layer. The service rejects clients outside the allowlist before executing any endpoint logic.

Authentication uses the standard bearer-token header:

```http
Authorization: Bearer YOUR_RANDOM_TOKEN
```

The comparison uses `hmac.compare_digest`:

```python
valid = (
    scheme.lower() == "bearer"
    and bool(supplied_token)
    and hmac.compare_digest(supplied_token, settings.token)
)
```

The token is not accepted in a URL or form body. URLs commonly appear in browser history, proxy logs, analytics, and screenshots; form bodies are better than query strings but do not follow the conventional HTTP authentication model.

The application also deliberately ignores forwarded-IP headers. Because it is not deployed behind a trusted reverse proxy, headers such as `X-Forwarded-For` must not be allowed to override the actual network peer address.

## Fixed endpoints instead of a generic command API

The server exposes a small, explicit set of actions:

| Method | Endpoint | Action |
|---|---|---|
| `GET` | `/healthz` | Check whether the service is running |
| `POST` | `/lock` | Lock the Windows session |
| `POST` | `/youtube` | Open YouTube in the default browser |
| `POST` | `/update` | Run silent `winget` upgrades |
| `POST` | `/clear-temp` | Clear deletable user temporary files |
| `POST` | `/restart` | Restart Windows after a short delay |
| `POST` | `/shutdown` | Shut down Windows after a short delay |
| `GET` | `/jobs/<id>` | Read the status of a queued job |

There is intentionally no endpoint like `/run?command=...`. A generic command endpoint would dramatically expand the attack surface and turn any authentication mistake into remote command execution.

## Keeping requests fast

Updates and filesystem cleanup can take much longer than a mobile HTTP request should remain open. The application therefore submits actions to a small `ThreadPoolExecutor` and immediately returns `202 Accepted`:

```json
{
  "action": "update",
  "job_id": "4c0a83b8ea52f914",
  "status": "queued"
}
```

The `Location` response header points to the matching job-status endpoint. This keeps the phone interface responsive and prevents long-running commands from occupying request threads.

The job collection is bounded so it cannot grow forever, and the worker pool is intentionally small to prevent many expensive Windows tasks from running at once.

## Rate limits and action cooldowns

Two related controls prevent accidental or abusive repetition:

- A sliding-window limiter caps the total requests received from a client.
- A per-action cooldown rejects duplicate taps for a short period.

This is especially important for restart, shutdown, application updates, and temporary-file cleanup. When an action is temporarily blocked, the service returns `429 Too Many Requests` with a `Retry-After` header.

## Production serving with Waitress

Flask's built-in server is intended for development. The finished project uses Waitress, a production WSGI server that works well on Windows:

```python
serve(
    create_app(settings),
    host=settings.bind_host,
    port=settings.port,
    threads=8,
    connection_limit=50,
    channel_timeout=30,
    clear_untrusted_proxy_headers=True,
    expose_tracebacks=False,
)
```

The limits are deliberately conservative because this is a personal control service, not a public web application.

Responses also include headers that disable caching, MIME sniffing, framing, and referrer leakage. Detailed exceptions are written to local logs instead of being returned to clients.

## Complete server code

The following is the complete Flask server used by the project. Save it as `remote_control_server.py`:

```python
from __future__ import annotations

import hmac
import ipaddress
import logging
import os
import secrets
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import webbrowser
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Callable, Mapping, Sequence

from flask import Flask, Response, g, jsonify, request


LOG = logging.getLogger("remote_control")
TAILSCALE_IPV4_NETWORK = ipaddress.ip_network("100.64.0.0/10")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MAX_REQUEST_BYTES = 2_048


class ConfigurationError(RuntimeError):
    """Raised when the server cannot start securely."""


def discover_tailscale_ipv4() -> str:
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"], check=True, capture_output=True,
            text=True, timeout=5, shell=False, creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ConfigurationError(
            "Set REMOTE_CONTROL_BIND_HOST to this computer's Tailscale IPv4 address."
        ) from exc

    for line in result.stdout.splitlines():
        candidate = line.strip()
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv4Address) and address in TAILSCALE_IPV4_NETWORK:
            return candidate
    raise ConfigurationError("No Tailscale IPv4 address was found.")


def parse_allowed_clients(value: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError as exc:
            raise ConfigurationError(f"Invalid allowed client address/network: {item!r}") from exc
    if not networks:
        raise ConfigurationError("REMOTE_CONTROL_ALLOWED_IPS must contain at least one address.")
    return tuple(networks)


@dataclass(frozen=True)
class Settings:
    token: str
    allowed_clients: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    bind_host: str
    port: int = 5000
    requests_per_minute: int = 30

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env
        token = values.get("REMOTE_CONTROL_TOKEN", "")
        if len(token) < 32 or len(token) > 512 or token.strip() != token:
            raise ConfigurationError(
                "REMOTE_CONTROL_TOKEN must be a 32-512 character secret without surrounding whitespace."
            )
        allowed_clients = parse_allowed_clients(values.get("REMOTE_CONTROL_ALLOWED_IPS", ""))
        bind_host = values.get("REMOTE_CONTROL_BIND_HOST", "").strip() or discover_tailscale_ipv4()
        try:
            bind_address = ipaddress.ip_address(bind_host)
        except ValueError as exc:
            raise ConfigurationError("REMOTE_CONTROL_BIND_HOST must be an IP address.") from exc

        allow_non_tailscale = values.get("REMOTE_CONTROL_ALLOW_NON_TAILSCALE_BIND") == "1"
        is_safe_default = bind_address.is_loopback or (
            isinstance(bind_address, ipaddress.IPv4Address)
            and bind_address in TAILSCALE_IPV4_NETWORK
        )
        if not is_safe_default and not allow_non_tailscale:
            raise ConfigurationError(
                "Refusing a non-Tailscale bind address. Set "
                "REMOTE_CONTROL_ALLOW_NON_TAILSCALE_BIND=1 only if you have secured that interface."
            )
        try:
            port = int(values.get("REMOTE_CONTROL_PORT", "5000"))
            rate = int(values.get("REMOTE_CONTROL_REQUESTS_PER_MINUTE", "30"))
        except ValueError as exc:
            raise ConfigurationError("Port and rate limit must be integers.") from exc
        if not 1 <= port <= 65_535:
            raise ConfigurationError("REMOTE_CONTROL_PORT must be between 1 and 65535.")
        if not 1 <= rate <= 600:
            raise ConfigurationError("REMOTE_CONTROL_REQUESTS_PER_MINUTE must be between 1 and 600.")
        return cls(token, allowed_clients, str(bind_address), port, rate)

    def allows(self, client: str | None) -> bool:
        if not client:
            return False
        try:
            address = ipaddress.ip_address(client)
        except ValueError:
            return False
        return any(address.version == network.version and address in network for network in self.allowed_clients)


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.events: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self.lock:
            events = self.events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - events[0])) + 1)
                return False, retry_after
            events.append(now)
            return True, 0


class ActionCooldown:
    def __init__(self) -> None:
        self.last_run: dict[tuple[str, str], float] = {}
        self.lock = threading.Lock()

    def acquire(self, client: str, action: str, cooldown_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        key = (client, action)
        with self.lock:
            previous = self.last_run.get(key)
            if previous is not None and now - previous < cooldown_seconds:
                return False, max(1, int(cooldown_seconds - (now - previous)) + 1)
            self.last_run[key] = now
            return True, 0


class ActionService:
    def __init__(self, workers: int = 2) -> None:
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="remote-action")
        self.jobs: dict[str, dict[str, str]] = {}
        self.lock = threading.Lock()

    def submit(self, action: str, work: Callable[[], object]) -> str:
        job_id = secrets.token_hex(8)
        with self.lock:
            if len(self.jobs) >= 100:
                self.jobs.pop(next(iter(self.jobs)), None)
            self.jobs[job_id] = {"id": job_id, "action": action, "status": "queued"}

        def execute() -> None:
            with self.lock:
                self.jobs[job_id]["status"] = "running"
            try:
                work()
            except Exception:
                LOG.exception("Action %s failed (job %s)", action, job_id)
                with self.lock:
                    self.jobs[job_id]["status"] = "failed"
            else:
                with self.lock:
                    self.jobs[job_id]["status"] = "completed"

        self.executor.submit(execute)
        return job_id

    def get_job(self, job_id: str) -> dict[str, str] | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None


def is_reparse_point(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def clear_temp_directory() -> dict[str, int]:
    target = Path(tempfile.gettempdir()).resolve(strict=True)
    dangerous = {Path(target.anchor).resolve(), Path.home().resolve(), Path.cwd().resolve()}
    windows_dir = os.environ.get("WINDIR")
    if windows_dir:
        dangerous.add(Path(windows_dir).resolve())
    if target in dangerous or len(target.parts) < 3 or not target.is_dir():
        raise RuntimeError(f"Refusing to clear unsafe temporary directory: {target}")

    deleted = skipped = 0
    for entry in target.iterdir():
        try:
            if entry.is_symlink() or is_reparse_point(entry):
                os.rmdir(entry) if entry.is_dir() else entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            deleted += 1
        except OSError:
            skipped += 1
    LOG.info("Temporary cleanup completed: %d deleted, %d skipped", deleted, skipped)
    return {"deleted": deleted, "skipped": skipped}


def create_app(settings: Settings) -> Flask:
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=MAX_REQUEST_BYTES,
        PROPAGATE_EXCEPTIONS=False,
        TRUSTED_HOSTS=[settings.bind_host, "127.0.0.1", "localhost"],
    )
    service = ActionService()
    request_limiter = SlidingWindowRateLimiter(settings.requests_per_minute, 60)
    auth_limiter = SlidingWindowRateLimiter(10, 60)
    cooldown = ActionCooldown()

    def problem(message: str, status: int, retry_after: int | None = None) -> Response:
        response = jsonify({"error": message, "status": status})
        response.status_code = status
        if retry_after is not None:
            response.headers["Retry-After"] = str(retry_after)
        return response

    @app.before_request
    def protect_request() -> Response | None:
        g.request_id = secrets.token_hex(8)
        if request.content_length is not None and request.content_length > MAX_REQUEST_BYTES:
            return problem("Request too large", 413)
        if not settings.allows(request.remote_addr):
            LOG.warning("Rejected request from a non-allowlisted client")
            return problem("Forbidden", 403)
        allowed, retry_after = request_limiter.allow(request.remote_addr or "unknown")
        if not allowed:
            return problem("Too many requests", 429, retry_after)
        return None

    @app.after_request
    def security_headers(response: Response) -> Response:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response

    def require_auth(handler: Callable[..., Response]) -> Callable[..., Response]:
        @wraps(handler)
        def wrapped(*args: object, **kwargs: object) -> Response:
            scheme, separator, supplied = request.headers.get("Authorization", "").partition(" ")
            valid = separator == " " and scheme.lower() == "bearer" and bool(supplied) and hmac.compare_digest(supplied, settings.token)
            if not valid:
                allowed, retry_after = auth_limiter.allow(request.remote_addr or "unknown")
                response = problem("Unauthorized", 401, None if allowed else retry_after)
                response.headers["WWW-Authenticate"] = 'Bearer realm="remote-control"'
                return response
            return handler(*args, **kwargs)
        return wrapped

    cooldowns = {"shutdown": 30, "restart": 30, "lock": 5, "update": 300, "clear-temp": 60, "youtube": 2}

    def queue(action: str, work: Callable[[], object]) -> Response:
        allowed, retry_after = cooldown.acquire(request.remote_addr or "unknown", action, cooldowns[action])
        if not allowed:
            return problem("Action is cooling down", 429, retry_after)
        job_id = service.submit(action, work)
        response = jsonify({"action": action, "job_id": job_id, "status": "queued"})
        response.status_code = 202
        response.headers["Location"] = f"/jobs/{job_id}"
        return response

    def command_work(command: Sequence[str], timeout_seconds: int) -> Callable[[], object]:
        fixed_command = tuple(command)
        def run() -> object:
            completed = subprocess.run(
                fixed_command, check=False, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
                timeout=timeout_seconds, shell=False, creationflags=NO_WINDOW,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"Command exited with status {completed.returncode}")
            return completed.returncode
        return run

    @app.get("/")
    @app.get("/healthz")
    def health() -> Response:
        return jsonify({"service": "remote-control", "status": "ok"})

    @app.post("/shutdown")
    @require_auth
    def shutdown() -> Response:
        return queue("shutdown", command_work(["shutdown.exe", "/s", "/t", "5", "/c", "Authorized remote shutdown"], 30))

    @app.post("/restart")
    @require_auth
    def restart() -> Response:
        return queue("restart", command_work(["shutdown.exe", "/r", "/t", "5", "/c", "Authorized remote restart"], 30))

    @app.post("/lock")
    @require_auth
    def lock() -> Response:
        return queue("lock", command_work(["rundll32.exe", "user32.dll,LockWorkStation"], 30))

    @app.post("/update")
    @require_auth
    def update() -> Response:
        return queue("update", command_work([
            "winget.exe", "upgrade", "--all", "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
            "--disable-interactivity",
        ], 7_200))

    @app.post("/clear-temp")
    @require_auth
    def clear_temp() -> Response:
        return queue("clear-temp", clear_temp_directory)

    @app.post("/youtube")
    @require_auth
    def youtube() -> Response:
        return queue("youtube", lambda: webbrowser.open_new_tab("https://www.youtube.com/"))

    @app.get("/jobs/<job_id>")
    @require_auth
    def job_status(job_id: str) -> Response:
        valid_id = len(job_id) == 16 and all(character in "0123456789abcdef" for character in job_id)
        if not valid_id:
            return problem("Not found", 404)
        job = service.get_job(job_id)
        return jsonify(job) if job else problem("Not found", 404)

    @app.errorhandler(404)
    def not_found(_error: Exception) -> Response:
        return problem("Not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_error: Exception) -> Response:
        return problem("Method not allowed", 405)

    @app.errorhandler(413)
    def too_large(_error: Exception) -> Response:
        return problem("Request too large", 413)

    @app.errorhandler(500)
    def internal_error(_error: Exception) -> Response:
        LOG.exception("Unhandled server error")
        return problem("Internal server error", 500)

    return app


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("REMOTE_CONTROL_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        settings = Settings.from_environment()
    except ConfigurationError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc
    try:
        from waitress import serve
    except ImportError as exc:
        raise SystemExit("Install dependencies first: python -m pip install -r requirements.txt") from exc

    LOG.info("Listening on http://%s:%d (Tailscale only)", settings.bind_host, settings.port)
    serve(
        create_app(settings), host=settings.bind_host, port=settings.port,
        threads=8, connection_limit=50, channel_timeout=30,
        cleanup_interval=10, clear_untrusted_proxy_headers=True,
        expose_tracebacks=False,
    )


if __name__ == "__main__":
    main()
```

## Getting started

The steps below build the project from an empty directory and finish with a working Android shortcut.

### 1. Install the prerequisites

Install the following on the Windows laptop:

- Python 3.12 or newer;
- Tailscale; and
- `winget`, if the update endpoint will be used.

Install Tailscale on the Android phone as well, sign in to the same tailnet on both devices, and confirm that both appear as connected.

### 2. Find both Tailscale addresses

On the laptop, run:

```powershell
tailscale ip -4
```

Copy the returned address. This becomes `REMOTE_CONTROL_BIND_HOST` and the host portion of every shortcut URL.

On Android, open Tailscale, select the phone, and copy its Tailscale IPv4 address. This becomes `REMOTE_CONTROL_ALLOWED_IPS`.

Do not use the phone's Wi-Fi address, mobile-data address, or public internet address. Tailscale IPv4 addresses normally fall within `100.64.0.0/10`.

### 3. Create the project and virtual environment

Create a folder for the service, place `remote_control_server.py` inside it, and open PowerShell in that directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install Flask==3.1.3 waitress==3.0.2
```

Create `requirements.txt` so the environment can be reproduced later:

```text
Flask==3.1.3
waitress==3.0.2
```

### 4. Generate a bearer token

Generate the secret locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output into a private `server.env` file:

```dotenv
REMOTE_CONTROL_TOKEN=PASTE_THE_GENERATED_TOKEN_HERE
REMOTE_CONTROL_ALLOWED_IPS=PHONE_TAILSCALE_IPV4
REMOTE_CONTROL_BIND_HOST=LAPTOP_TAILSCALE_IPV4
REMOTE_CONTROL_PORT=5000
REMOTE_CONTROL_REQUESTS_PER_MINUTE=30
```

Add `server.env`, `.venv/`, `__pycache__/`, and `*.pyc` to `.gitignore`. Never publish the real environment file or paste its token into a blog post, issue, or public repository.

### 5. Create a launcher

PowerShell does not automatically load dotenv-style files, so save the following as `start.ps1`:

```powershell
$ErrorActionPreference = "Stop"
$ProjectDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectDirectory ".venv\Scripts\python.exe"
$EnvironmentFile = Join-Path $ProjectDirectory "server.env"

if (-not (Test-Path -LiteralPath $Python)) { throw "The virtual environment is missing." }
if (-not (Test-Path -LiteralPath $EnvironmentFile)) { throw "server.env is missing." }

foreach ($Line in Get-Content -LiteralPath $EnvironmentFile) {
    $Trimmed = $Line.Trim()
    if (-not $Trimmed -or $Trimmed.StartsWith("#")) { continue }
    $Parts = $Trimmed.Split("=", 2)
    if ($Parts.Count -ne 2 -or -not $Parts[0]) { throw "Invalid server.env line." }
    [Environment]::SetEnvironmentVariable($Parts[0], $Parts[1], "Process")
}

& $Python (Join-Path $ProjectDirectory "remote_control_server.py")
```

Start the server:

```powershell
.\start.ps1
```

The console should report that Waitress is listening on the laptop's Tailscale address. Leave this first test instance running while configuring the phone.

### 6. Check basic connectivity

With Tailscale connected on the phone, open this address in the phone's browser, replacing the placeholder with the laptop address:

```text
http://LAPTOP_TAILSCALE_IPV4:5000/healthz
```

The expected response is:

```json
{"service":"remote-control","status":"ok"}
```

If the request is forbidden, verify that `REMOTE_CONTROL_ALLOWED_IPS` contains the phone's current Tailscale address. If it times out, confirm that Tailscale is connected on both devices and that the server is bound to the correct laptop address.

### 7. Create the first Android shortcut

In HTTP Shortcuts, add a regular HTTP shortcut with these settings:

| Setting | Value |
|---|---|
| Name | Open YouTube |
| Method | `POST` |
| URL | `http://LAPTOP_TAILSCALE_IPV4:5000/youtube` |
| Authentication | Bearer Authentication |
| Token | The value from `REMOTE_CONTROL_TOKEN` |
| Follow redirects | Off |
| Store cookies | Off |
| Timeout | `10000` milliseconds |

Use a complete literal URL. Some versions or synchronization paths in HTTP Shortcuts may not expand editor variables consistently.

Test **Open YouTube** first because it is non-destructive. A successful request returns `202 Accepted`, and YouTube opens in the laptop's default browser.

### 8. Add the remaining shortcuts

Duplicate the working shortcut and change only its name and endpoint:

| Shortcut | Endpoint |
|---|---|
| Lock Laptop | `/lock` |
| Update Apps | `/update` |
| Clear Temp Files | `/clear-temp` |
| Restart Laptop | `/restart` |
| Shut Down Laptop | `/shutdown` |

Keep the method, bearer token, redirect setting, cookie setting, and timeout identical. Test lock before testing restart or shutdown.

### 9. Run it without a terminal window

Once the visible version works, use `pythonw.exe` through a per-user Scheduled Task. Save this as `background_launcher.pyw`:

```python
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

def load_environment() -> None:
    environment_file = PROJECT_DIR / "server.env"
    for raw_line in environment_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if separator != "=" or not name:
            raise RuntimeError("Invalid line in server.env")
        os.environ[name] = value

os.chdir(PROJECT_DIR)
load_environment()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[RotatingFileHandler(
        PROJECT_DIR / "remote_control.log", maxBytes=1_000_000,
        backupCount=3, encoding="utf-8",
    )],
)

from remote_control_server import main
main()
```

Then register it to run at sign-in:

```powershell
$TaskName = "Tailscale Laptop Remote Control"
$ProjectDirectory = (Get-Location).Path
$PythonWindowed = Join-Path $ProjectDirectory ".venv\Scripts\pythonw.exe"
$Launcher = Join-Path $ProjectDirectory "background_launcher.pyw"
$Account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$Action = New-ScheduledTaskAction `
    -Execute $PythonWindowed `
    -Argument ('"{0}"' -f $Launcher) `
    -WorkingDirectory $ProjectDirectory
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $Account
$Principal = New-ScheduledTaskPrincipal `
    -UserId $Account -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew -Hidden

Register-ScheduledTask `
    -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Principal $Principal -Settings $Settings `
    -Description "Secure Tailscale-only laptop remote control server" -Force
```

Stop the visible `start.ps1` instance before starting the scheduled task, otherwise both processes will compete for port `5000`:

```powershell
Start-ScheduledTask -TaskName "Tailscale Laptop Remote Control"
```

Confirm that it is running:

```powershell
Get-ScheduledTask -TaskName "Tailscale Laptop Remote Control"
Get-NetTCPConnection -State Listen -LocalPort 5000
```

The server now starts automatically after Windows sign-in, remains in the interactive user session so browser actions work, and does not leave a terminal window open.

## Configuring HTTP Shortcuts on Android

Each shortcut uses:

- method: `POST`;
- a literal URL, such as `http://100.a.b.c:5000/lock`;
- authentication method: Bearer Authentication;
- the generated token;
- redirects disabled;
- cookie storage disabled; and
- a short request timeout.

I initially used editor variables in the URL, but the Android app treated the variable expression as literal text after synchronizing the configuration. Using complete literal URLs proved more reliable for this setup.

An equivalent cURL command looks like this:

```bash
curl --request POST \
  --url "http://100.a.b.c:5000/lock" \
  --header "Authorization: Bearer YOUR_RANDOM_TOKEN"
```

HTTP Shortcuts can import a command like this and automatically populate the request method, URL, and header.

When editing shortcuts through the desktop web editor, the safe synchronization order matters:

1. Save the corrected configuration in the editor.
2. On the phone, select **Pull Changes**.
3. Do not select **Push Changes** first, because that could overwrite the newer server-side configuration with the older phone copy.
4. Test a harmless action such as opening YouTube before testing shutdown or restart.

## Running invisibly at Windows sign-in

The server originally required an open PowerShell window. To make it unobtrusive, I added a small `.pyw` launcher and registered it as a per-user Windows Scheduled Task.

The task:

- starts when the current user signs in;
- runs with `pythonw.exe`, so no console window appears;
- runs in the interactive user session, allowing the browser-opening action to work;
- ignores duplicate task launches;
- restarts automatically after a failure; and
- writes to a rotating local log file.

This is a better fit than a Windows service for this particular project. A true Windows service runs in a separate non-interactive session, which makes opening a browser in the signed-in desktop unreliable or impossible.

The scheduled-task action points directly to the windowless Python executable:

```powershell
$Action = New-ScheduledTaskAction `
    -Execute ".venv\Scripts\pythonw.exe" `
    -Argument '"background_launcher.pyw"' `
    -WorkingDirectory $ProjectDirectory
```

The launcher loads the private environment file, configures rotating logs, and then starts the same application entry point used by the visible development launcher.

## Testing the security boundary

The project includes focused tests for the behaviors that matter most:

- a non-allowlisted source address receives `403 Forbidden`;
- missing and incorrect bearer tokens receive `401 Unauthorized`;
- a token submitted as form data is rejected;
- valid requests queue only fixed command arrays;
- repeated actions receive `429 Too Many Requests`;
- oversized requests receive `413 Request Entity Too Large`;
- job identifiers are authenticated and validated;
- security headers appear on responses; and
- temporary cleanup preserves its root directory while deleting its children.

I also tested a forged `X-Forwarded-For` header. The request remained forbidden, confirming that the application uses the actual peer address rather than trusting a client-supplied proxy header.

Destructive actions were not executed as part of automated testing. Instead, the test suite injects a fake action service and verifies the exact fixed command that would have been queued.

## Limitations and future improvements

This design is intentionally narrow, but a few limitations remain:

- The bearer token is stored on both trusted endpoints. If either device is compromised, rotate it.
- Tailscale encrypts traffic between the devices, but the application itself uses HTTP rather than application-level HTTPS. It must remain private to the tailnet.
- Source-IP allowlisting assumes the phone keeps the same Tailscale address. Update the configuration if that address changes.
- In-memory rate limits and job records reset when the server restarts.
- Silent `winget` upgrades may skip packages that require elevation or user interaction.
- Opening a browser depends on the task running in the signed-in user's interactive session.

Possible future improvements include checking Tailscale identity information instead of a fixed IP address, persisting job history in SQLite, adding Windows event-log integration, and rotating bearer tokens through a simple administrative workflow.

## Lessons learned

The biggest lesson was that a working local automation script is not automatically safe enough to become a network service. The dangerous part was not Flask itself; it was the combination of network exposure, powerful operating-system actions, credential handling, and destructive filesystem operations.

The hardened version stays manageable because it keeps the feature set deliberately small:

- one private interface;
- one approved client;
- one strong token;
- six fixed actions; and
- no user-controlled commands.

That narrow design is what makes the service practical to secure. Tailscale provides the private transport, Flask provides a clean HTTP interface, Waitress provides a reliable Windows server, and HTTP Shortcuts turns the phone into a simple remote-control panel.

For a personal automation project, it is a satisfying combination and a good reminder that convenience and security do not have to be opposites when the boundaries are designed carefully.

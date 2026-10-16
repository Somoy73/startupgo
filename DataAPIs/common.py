"""Shared HTTP helper and scraper registry (stdlib only, no installs needed)."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

UA = os.environ.get("SCRAPER_USER_AGENT", "OceanOpportunityRadar/0.1 (contact: mayajshetty@gmail.com)")
TIMEOUT = 75


class Skipped(Exception):
    """Raised when a scraper cannot run (missing API key etc.)."""


def http(url: str, params: dict | None = None, *, method: str = "GET", json_body: Any = None,
         form: dict | None = None, multipart: dict | None = None, headers: dict | None = None,
         auth: tuple[str, str] | None = None, raw: bool = False) -> Any:
    """Return parsed JSON when possible, else text. `raw=True` always returns text."""
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(clean, doseq=True)
    h = {"User-Agent": UA, "Accept": "application/json, */*"}
    h.update(headers or {})
    cmd = ["curl", "-sS", "-L", "--max-time", str(TIMEOUT), "-X", method, "-w", "\n%{http_code}"]
    body_in = None
    if json_body is not None:
        body_in = json.dumps(json_body)
        h["Content-Type"] = "application/json"
    elif form is not None:
        body_in = urllib.parse.urlencode(form)
        h["Content-Type"] = "application/x-www-form-urlencoded"
    elif multipart is not None:
        b = uuid.uuid4().hex
        body_in = "".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{k}"\r\n'
                          f'Content-Type: application/json\r\n\r\n{v}\r\n' for k, v in multipart.items()) + f"--{b}--\r\n"
        h["Content-Type"] = f"multipart/form-data; boundary={b}"
    if auth:
        cmd += ["-u", f"{auth[0]}:{auth[1]}"]
    for k, v in h.items():
        cmd += ["-H", f"{k}: {v}"]
    if body_in is not None:
        cmd += ["--data-binary", "@-"]
    cmd.append(url)
    p = subprocess.run(cmd, input=body_in, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError(f"curl failed ({p.returncode}): {p.stderr.strip()[:300]}")
    body, _, code = p.stdout.rpartition("\n")
    if not code.startswith("2"):
        raise RuntimeError(f"HTTP {code}: {body[:300]}")
    if raw:
        return body
    try:
        return json.loads(body)
    except ValueError:
        return body


def need(env: str) -> str:
    v = os.environ.get(env)
    if not v:
        raise Skipped(f"set env var {env}")
    return v


@dataclass
class Source:
    name: str
    section: str
    access: str          # free | key | paid
    endpoint: str
    use: str
    params: dict[str, str]          # upstream query params you can pass (name -> meaning)
    defaults: dict[str, Any]        # what the sample run uses
    fn: Callable[..., Any] | None = None
    slow: bool = False              # polite delay needed afterwards
    notes: str = ""


REGISTRY: list[Source] = []


def source(**meta):
    def deco(fn):
        REGISTRY.append(Source(fn=fn, **meta))
        return fn
    return deco

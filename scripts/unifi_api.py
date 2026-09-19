#!/usr/bin/env python3
"""Authenticated read access to the UDM's Network API.

Shared by every consumer that talks to the controller. Callers supply their own
interpretation of the payloads; this module owns only the login, the proxy path,
and turning a failed request into a message that is safe to print.
"""

from dataclasses import dataclass
import os
from typing import Protocol
from urllib.parse import urlparse

import httpx

DEFAULT_API_URL = "https://10.10.20.1"
NETWORK_API_PREFIX = "/proxy/network/api/s/default"
HTTP_TIMEOUT = 15.0
HTTP_OK = 200


class ControllerError(Exception):
    """The controller could not be reached or answered unusably.

    The message never carries credentials or response bodies, so it is safe to
    print anywhere.
    """


class JsonSource(Protocol):
    def get_json(self, path: str) -> object: ...


def decode_json(response: httpx.Response, what: str) -> object:
    try:
        return response.json()
    except ValueError:
        raise ControllerError(f"{what}: response body was not JSON") from None


@dataclass(frozen=True)
class NetworkApi:
    """Reads the legacy Network API through the UniFi OS proxy."""

    client: httpx.Client
    base_url: str

    def get_json(self, path: str) -> object:
        response = self.client.get(f"{self.base_url}{NETWORK_API_PREFIX}{path}")
        if response.status_code != HTTP_OK:
            raise ControllerError(f"GET {path}: HTTP {response.status_code}")
        return decode_json(response, f"GET {path}")


def login(client: httpx.Client, base_url: str, username: str, password: str) -> str:
    response = client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password, "rememberMe": False},
    )
    if response.status_code != HTTP_OK:
        raise ControllerError(f"login rejected with HTTP {response.status_code}")
    if not client.cookies.jar:
        raise ControllerError("login returned no session cookie")
    csrf_token = response.headers.get("x-updated-csrf-token") or response.headers.get(
        "x-csrf-token"
    )
    if csrf_token:
        client.headers["X-CSRF-Token"] = csrf_token
    return "authenticated to controller"


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ControllerError(f"{name} is not set")
    return value


def controller_base_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ControllerError(
            "TF_VAR_unifi_api_url must be an HTTPS origin without credentials, "
            "a path, a query, or a fragment"
        )
    return value.rstrip("/")

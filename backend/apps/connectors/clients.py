import base64
import ipaddress
import json
import os
import re
import socket
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from rest_framework.exceptions import ValidationError

from .models import ConnectorConfig
from .normalizers import (
    normalize_active_directory,
    normalize_fortigate,
    normalize_tenable,
    normalize_veeam,
)


_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

FORTIGATE_COLLECTION_PROFILES = {
    "minimal": ["/api/v2/cmdb/system/global"],
    "baseline": [
        "/api/v2/monitor/system/status",
        "/api/v2/cmdb/system/admin",
        "/api/v2/cmdb/firewall/policy",
        "/api/v2/cmdb/system/interface",
    ],
}


@dataclass
class ConnectorResult:
    title: str
    payload: dict


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValidationError(f"Connector redirects are disabled (HTTP {code}).")


def validate_secret_env_name(name):
    if name and not _ENV_NAME_RE.fullmatch(str(name)):
        raise ValidationError("Connector credentials must reference a valid environment-variable name, not a literal secret.")
    return name


def _normalize_ip(address):
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return ip.ipv4_mapped
    return ip


def validate_network_target(hostname, port):
    if not hostname:
        raise ValidationError("Connector target hostname is required.")
    lowered = str(hostname).strip().lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"}:
        raise ValidationError("Connector target cannot be localhost.")
    try:
        infos = socket.getaddrinfo(lowered, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValidationError(f"Connector hostname could not be resolved: {exc}") from exc

    addresses = {_normalize_ip(info[4][0]) for info in infos}
    if not addresses:
        raise ValidationError("Connector hostname did not resolve to an address.")

    # Private RFC1918/ULA targets are intentionally allowed for on-prem connectors.
    # Loopback, link-local/cloud-metadata, multicast, unspecified and reserved targets are not.
    for ip in addresses:
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ValidationError(f"Connector target resolves to a prohibited address class: {ip}.")
    return addresses


def validate_http_base_url(base_url):
    parsed = urllib.parse.urlparse(str(base_url or "").strip())
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValidationError("Connector base_url must be an http(s) URL with a hostname.")
    if parsed.username or parsed.password:
        raise ValidationError("Connector credentials must not be embedded in base_url.")
    if parsed.query or parsed.fragment:
        raise ValidationError("Connector base_url must not contain a query string or fragment.")
    if parsed.scheme != "https" and getattr(settings, "APP_ENV", "development") == "production":
        raise ValidationError("Production HTTP connectors must use HTTPS.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    validate_network_target(parsed.hostname, port)
    return parsed


class BaseConnector:
    def __init__(self, config):
        self.config = config

    def _secret(self, name):
        validate_secret_env_name(name)
        return os.getenv(name, "") if name else ""

    def collect(self):
        raise NotImplementedError

    def health(self):
        self.collect()
        return {"ok": True}

    def _json(self, path, *, headers=None, method="GET", data=None):
        validate_http_base_url(self.config.base_url)
        if not isinstance(path, str) or not path.startswith("/") or "\r" in path or "\n" in path:
            raise ValidationError("Connector request path must be a safe absolute path on the configured host.")
        path_parts = urllib.parse.urlsplit(path)
        if path_parts.scheme or path_parts.netloc:
            raise ValidationError("Connector request path cannot override the configured host.")

        base = self.config.base_url.rstrip("/")
        url = base + path
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        context = ssl.create_default_context() if self.config.verify_tls else ssl._create_unverified_context()
        if not self.config.verify_tls and getattr(settings, "APP_ENV", "development") == "production":
            raise ValidationError("TLS verification cannot be disabled for production HTTP connectors.")
        max_bytes = int(getattr(settings, "CONNECTOR_MAX_RESPONSE_BYTES", 5 * 1024 * 1024))
        opener = urllib.request.build_opener(
            _NoRedirect,
            urllib.request.HTTPSHandler(context=context),
            urllib.request.HTTPHandler(),
        )
        try:
            with opener.open(req, timeout=getattr(settings, "CONNECTOR_HTTP_TIMEOUT", 30)) as response:
                raw_bytes = response.read(max_bytes + 1)
                if len(raw_bytes) > max_bytes:
                    raise ValidationError("Connector response exceeded the configured size limit.")
                raw = raw_bytes.decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}, response.headers
        except ValidationError:
            raise
        except Exception as exc:
            raise ValidationError(f"Connector request failed: {exc}") from exc


class FortiGateConnector(BaseConnector):
    def collect(self):
        token = self._secret(self.config.secret_env_var)
        if not token:
            raise ValidationError("FortiGate API token secret is missing.")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
        cfg = self.config.configuration or {}
        profile = cfg.get("collection_profile") or "baseline"
        paths = cfg.get("read_paths") or FORTIGATE_COLLECTION_PROFILES.get(profile)
        if not paths:
            raise ValidationError("Unknown FortiGate collection_profile and no read_paths were supplied.")
        if len(paths) > 10:
            raise ValidationError("At most 10 FortiGate read paths are allowed per run.")
        results = {}
        for path in paths:
            if not isinstance(path, str) or not path.startswith("/api/v2/"):
                raise ValidationError("FortiGate connector permits only /api/v2/ read paths.")
            data, _ = self._json(path, headers=headers)
            results[path] = data
        return ConnectorResult("FortiGate security configuration snapshot", normalize_fortigate(results))


class TenableConnector(BaseConnector):
    def collect(self):
        access = self._secret(self.config.username_env_var)
        secret = self._secret(self.config.secret_env_var)
        if not access or not secret:
            raise ValidationError("Tenable access/secret key environment variables are required.")
        headers = {"Accept": "application/json", "X-ApiKeys": f"accessKey={access}; secretKey={secret}"}
        data, _ = self._json("/scans", headers=headers)
        return ConnectorResult("Tenable / Nessus scan inventory", normalize_tenable(data))


class VeeamConnector(BaseConnector):
    def _session(self):
        username = self._secret(self.config.username_env_var)
        password = self._secret(self.config.secret_env_var)
        if not username or not password:
            raise ValidationError("Veeam username/password environment variables are required.")
        auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        _, headers = self._json(
            "/api/sessionMngr/?v=latest",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
            method="POST",
            data=b"",
        )
        token = headers.get("X-RestSvcSessionId")
        if not token:
            raise ValidationError("Veeam did not return X-RestSvcSessionId.")
        return token

    def collect(self):
        token = self._session()
        headers = {"Accept": "application/json", "X-RestSvcSessionId": token}
        backups, _ = self._json("/api/backups", headers=headers)
        sessions, _ = self._json("/api/backupSessions", headers=headers)
        return ConnectorResult("Veeam backup assurance snapshot", normalize_veeam(backups, sessions))


class ActiveDirectoryConnector(BaseConnector):
    def collect(self):
        try:
            from ldap3 import ALL, Connection, Server, SUBTREE
        except ImportError as exc:
            raise ValidationError("ldap3 package is required for the Active Directory connector.") from exc

        username = self._secret(self.config.username_env_var)
        password = self._secret(self.config.secret_env_var)
        cfg = self.config.configuration or {}
        host = cfg.get("host") or self.config.base_url
        base_dn = cfg.get("base_dn")
        use_ssl = bool(cfg.get("use_ssl", True))

        if isinstance(host, str) and "://" in host:
            parsed = urllib.parse.urlparse(host)
            if parsed.username or parsed.password:
                raise ValidationError("AD credentials must not be embedded in the host URL.")
            host = parsed.hostname or host
        if not host or not base_dn:
            raise ValidationError("AD connector requires host/base_dn configuration.")

        validate_network_target(host, int(cfg.get("port") or (636 if use_ssl else 389)))
        server = Server(
            host,
            port=int(cfg.get("port") or (636 if use_ssl else 389)),
            use_ssl=use_ssl,
            get_info=ALL,
            connect_timeout=getattr(settings, "CONNECTOR_HTTP_TIMEOUT", 30),
        )
        conn = Connection(
            server,
            user=username or None,
            password=password or None,
            auto_bind=True,
            receive_timeout=getattr(settings, "CONNECTOR_HTTP_TIMEOUT", 30),
        )
        search_filter = cfg.get("search_filter") or "(&(objectCategory=person)(objectClass=user))"
        attributes = cfg.get("attributes") or [
            "distinguishedName",
            "sAMAccountName",
            "userPrincipalName",
            "userAccountControl",
            "memberOf",
            "whenChanged",
        ]
        conn.search(
            base_dn,
            search_filter,
            search_scope=SUBTREE,
            attributes=attributes,
            size_limit=min(int(cfg.get("size_limit", 5000)), 10000),
        )
        rows = []
        for entry in conn.entries:
            record = {}
            for attr in attributes:
                if attr not in entry:
                    continue
                value = entry[attr].value
                if isinstance(value, (list, tuple, set)):
                    record[attr] = [str(item) for item in value]
                elif value is not None:
                    record[attr] = str(value)
            rows.append(record)
        conn.unbind()
        payload = normalize_active_directory(
            rows,
            privileged_groups=cfg.get("privileged_groups") or [],
            include_sample=bool(cfg.get("include_sample", False)),
        )
        return ConnectorResult("Active Directory account hygiene snapshot", payload)


def connector_for(config):
    mapping = {
        ConnectorConfig.ConnectorType.FORTIGATE: FortiGateConnector,
        ConnectorConfig.ConnectorType.TENABLE: TenableConnector,
        ConnectorConfig.ConnectorType.VEEAM: VeeamConnector,
        ConnectorConfig.ConnectorType.ACTIVE_DIRECTORY: ActiveDirectoryConnector,
    }
    cls = mapping.get(config.connector_type)
    if not cls:
        raise ValidationError("Unsupported connector type.")
    return cls(config)

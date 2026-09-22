from collections import Counter


CONTRACT_SCHEMA_VERSION = "1.0"


def _as_list(value, *candidate_keys):
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        return []
    for key in candidate_keys:
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            nested = _as_list(candidate, "Refs", "Entities", "items", "data", "results")
            if nested:
                return nested
    for key in ("results", "data", "items", "Refs", "Entities"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
    return []


def _pick(row, *names, default=None):
    if not isinstance(row, dict):
        return default
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _enabled(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "enable", "enabled", "up", "active"}


def _fortigate_records(path_payloads, fragment):
    for path, payload in path_payloads.items():
        if fragment in path:
            if isinstance(payload, dict) and isinstance(payload.get("results"), dict):
                return [payload["results"]]
            return _as_list(payload, "results")
    return []


def normalize_fortigate(path_payloads):
    path_payloads = path_payloads or {}
    status_rows = _fortigate_records(path_payloads, "/monitor/system/status")
    global_rows = _fortigate_records(path_payloads, "/cmdb/system/global")
    admins = _fortigate_records(path_payloads, "/cmdb/system/admin")
    policies = _fortigate_records(path_payloads, "/cmdb/firewall/policy")
    interfaces = _fortigate_records(path_payloads, "/cmdb/system/interface")

    device = (status_rows or global_rows or [{}])[0]
    two_factor_admins = []
    admin_sample = []
    for row in admins[:100]:
        two_factor = _pick(row, "two-factor", "two_factor", "twoFactor", default="")
        has_two_factor = str(two_factor or "").strip().lower() not in {"", "0", "none", "disable", "disabled"}
        name = str(_pick(row, "name", "admin", default=""))
        if has_two_factor and name:
            two_factor_admins.append(name)
        admin_sample.append(
            {
                "name": name,
                "profile": _pick(row, "accprofile", "access_profile", "profile"),
                "two_factor_configured": has_two_factor,
            }
        )

    enabled_policies = 0
    logging_policies = 0
    policy_sample = []
    for row in policies[:200]:
        if _enabled(_pick(row, "status", default="enable")):
            enabled_policies += 1
        log_value = str(_pick(row, "logtraffic", "log_traffic", default="")).strip().lower()
        if log_value not in {"", "0", "disable", "disabled", "none"}:
            logging_policies += 1
        policy_sample.append(
            {
                "id": _pick(row, "policyid", "id"),
                "name": _pick(row, "name"),
                "status": _pick(row, "status"),
                "action": _pick(row, "action"),
                "logtraffic": _pick(row, "logtraffic", "log_traffic"),
                "utm_status": _pick(row, "utm-status", "utm_status"),
            }
        )

    interface_sample = []
    interface_up_count = 0
    for row in interfaces[:200]:
        status = _pick(row, "status", "link", default="")
        if _enabled(status):
            interface_up_count += 1
        interface_sample.append(
            {
                "name": _pick(row, "name"),
                "status": status,
                "role": _pick(row, "role"),
                "allowaccess": _pick(row, "allowaccess"),
            }
        )

    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "provider": "fortigate",
        "dataset": "security_configuration",
        "summary": {
            "admin_count": len(admins),
            "admins_with_two_factor_count": len(two_factor_admins),
            "policy_count": len(policies),
            "enabled_policy_count": enabled_policies,
            "policies_with_logging_count": logging_policies,
            "interface_count": len(interfaces),
            "interface_up_count": interface_up_count,
        },
        "device": {
            "hostname": _pick(device, "hostname", "name"),
            "serial": _pick(device, "serial", "serial_number"),
            "version": _pick(device, "version"),
            "build": _pick(device, "build"),
            "model": _pick(device, "model_name", "model"),
        },
        "administrators": admin_sample,
        "policies": policy_sample,
        "interfaces": interface_sample,
        "source_paths": sorted(path_payloads.keys()),
    }


def normalize_tenable(scan_payload):
    scans = _as_list(scan_payload or {}, "scans")
    status_counts = Counter()
    normalized_scans = []
    most_recent = None
    for row in scans[:500]:
        status = str(_pick(row, "status", default="unknown") or "unknown").lower()
        status_counts[status] += 1
        modified = _pick(row, "last_modification_date", "last_modified", "timestamp")
        if modified is not None and (most_recent is None or str(modified) > str(most_recent)):
            most_recent = modified
        normalized_scans.append(
            {
                "id": _pick(row, "id"),
                "name": _pick(row, "name"),
                "status": status,
                "last_modification_date": modified,
                "folder_id": _pick(row, "folder_id", "folder"),
                "owner": _pick(row, "owner"),
            }
        )
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "provider": "tenable",
        "dataset": "scan_inventory",
        "summary": {
            "scan_count": len(scans),
            "status_counts": dict(sorted(status_counts.items())),
            "most_recent_modification": most_recent,
        },
        "scans": normalized_scans,
    }


def _veeam_rows(payload, *keys):
    rows = _as_list(payload, *keys)
    if rows:
        return rows
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                rows = _as_list(value, *keys, "Refs", "Entities")
                if rows:
                    return rows
    return []


def normalize_veeam(backups_payload, sessions_payload):
    backups = _veeam_rows(backups_payload or {}, "Backups", "backups")
    sessions = _veeam_rows(sessions_payload or {}, "BackupSessions", "backupSessions", "sessions")
    result_counts = Counter()
    state_counts = Counter()
    normalized_sessions = []
    for row in sessions[:500]:
        result = str(_pick(row, "Result", "result", default="unknown") or "unknown").lower()
        state = str(_pick(row, "State", "state", default="unknown") or "unknown").lower()
        result_counts[result] += 1
        state_counts[state] += 1
        normalized_sessions.append(
            {
                "id": _pick(row, "UID", "uid", "Id", "id"),
                "name": _pick(row, "Name", "name"),
                "result": result,
                "state": state,
                "creation_time": _pick(row, "CreationTimeUTC", "creation_time", "start_time"),
                "end_time": _pick(row, "EndTimeUTC", "end_time"),
            }
        )

    normalized_backups = []
    for row in backups[:500]:
        normalized_backups.append(
            {
                "id": _pick(row, "UID", "uid", "Id", "id"),
                "name": _pick(row, "Name", "name"),
                "type": _pick(row, "Type", "type"),
            }
        )

    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "provider": "veeam",
        "dataset": "backup_assurance",
        "summary": {
            "backup_count": len(backups),
            "session_count": len(sessions),
            "session_result_counts": dict(sorted(result_counts.items())),
            "session_state_counts": dict(sorted(state_counts.items())),
        },
        "backups": normalized_backups,
        "backup_sessions": normalized_sessions,
    }


def _membership_values(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    text = str(value)
    if not text or text.lower() == "none":
        return []
    return [text]


def _matches_privileged_group(memberships, privileged_groups):
    if not privileged_groups:
        return False
    normalized_memberships = [item.strip().lower() for item in memberships]
    for group in privileged_groups:
        wanted = str(group).strip().lower()
        for membership in normalized_memberships:
            if membership == wanted or membership.startswith(f"cn={wanted},"):
                return True
    return False


def normalize_active_directory(rows, *, privileged_groups=None, include_sample=False):
    privileged_groups = privileged_groups or []
    disabled = 0
    password_not_required = 0
    password_never_expires = 0
    privileged = 0
    samples = []

    for row in rows or []:
        try:
            uac = int(str(_pick(row, "userAccountControl", default=0) or 0))
        except (TypeError, ValueError):
            uac = 0
        is_disabled = bool(uac & 0x0002)
        no_password_required = bool(uac & 0x0020)
        password_never_expires_flag = bool(uac & 0x10000)
        memberships = _membership_values(_pick(row, "memberOf", default=[]))
        is_privileged = _matches_privileged_group(memberships, privileged_groups)

        disabled += int(is_disabled)
        password_not_required += int(no_password_required)
        password_never_expires += int(password_never_expires_flag)
        privileged += int(is_privileged)
        if include_sample and len(samples) < 100:
            samples.append(
                {
                    "account": _pick(row, "sAMAccountName", "userPrincipalName"),
                    "disabled": is_disabled,
                    "password_not_required": no_password_required,
                    "password_never_expires": password_never_expires_flag,
                    "privileged_group_match": is_privileged,
                    "when_changed": _pick(row, "whenChanged"),
                }
            )

    result = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "provider": "active_directory",
        "dataset": "account_hygiene",
        "summary": {
            "user_count": len(rows or []),
            "disabled_count": disabled,
            "password_not_required_count": password_not_required,
            "password_never_expires_count": password_never_expires,
            "privileged_user_count": privileged,
        },
        "privileged_groups_evaluated": [str(group) for group in privileged_groups],
    }
    if include_sample:
        result["sample"] = samples
    return result

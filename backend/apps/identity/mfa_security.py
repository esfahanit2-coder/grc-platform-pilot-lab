import hmac

import pyotp
from django.db import transaction
from django.utils import timezone

from .models import MFADevice
from .services import decrypt_mfa_secret


@transaction.atomic
def verify_mfa_device_once(device, otp, *, valid_window=1):
    """Verify a TOTP once and atomically consume its matched time-step.

    The row lock and persisted last_used_step prevent the same accepted TOTP
    from being replayed across concurrent workers during its validity window.
    """
    submitted = str(otp or "").strip()
    if not submitted:
        return False

    locked = MFADevice.objects.select_for_update().filter(pk=device.pk).first()
    if locked is None:
        return False

    secret = decrypt_mfa_secret(locked.encrypted_secret)
    totp = pyotp.TOTP(secret)
    now = timezone.now()
    current_step = int(now.timestamp() // totp.interval)
    matched_step = None

    for offset in range(-int(valid_window), int(valid_window) + 1):
        candidate_step = current_step + offset
        candidate_code = totp.at(candidate_step * totp.interval)
        if hmac.compare_digest(candidate_code, submitted):
            matched_step = candidate_step
            break

    if matched_step is None:
        return False
    if locked.last_used_step is not None and matched_step <= locked.last_used_step:
        return False

    locked.last_used_step = matched_step
    locked.last_used_at = now
    locked.save(update_fields=["last_used_step", "last_used_at", "updated_at"])
    device.last_used_step = matched_step
    device.last_used_at = now
    return True

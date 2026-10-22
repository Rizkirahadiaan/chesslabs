import secrets
from datetime import timedelta

from sqlalchemy import select, func

from .core.security import digest, new_key, normalize_key
from .db import utcnow
from .models import License, Activation, Product, Customer, Plan, Renewal, AuditLog
from .repositories import locked_license


class DomainError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


TRANSITIONS = {
    "PENDING": {"ACTIVE", "SUSPENDED", "REVOKED"},
    "ACTIVE": {"EXPIRED", "SUSPENDED", "REVOKED"},
    "EXPIRED": {"ACTIVE", "SUSPENDED", "REVOKED"},
    "SUSPENDED": {"REVOKED"}, "REVOKED": set(),
}


def audit(db, action, resource, actor="system", actor_type="admin", details=None):
    db.add(AuditLog(actor_type=actor_type, actor_id=str(actor), action=action,
                    resource_type=resource.__tablename__, resource_id=str(resource.id), details=details or {}))


def transition(db, item, state, actor="server", actor_type="system", details=None):
    if state not in TRANSITIONS[item.status]:
        raise DomainError("INVALID_TRANSITION", "Perubahan status lisensi tidak diizinkan.", 409)
    previous = item.status
    item.status = state
    audit(db, "license." + state.lower(), item, actor, actor_type, dict(previous=previous, **(details or {})))


def effective_status(item, now=None):
    now = now or utcnow()
    if item.status == "ACTIVE" and item.expires_at <= now:
        return "EXPIRED"
    return item.status


def expire(db, item, now):
    if effective_status(item, now) == "EXPIRED" and item.status == "ACTIVE":
        transition(db, item, "EXPIRED")


def eligible(db, item, product_code):
    product = db.get(Product, item.product_id)
    customer = db.get(Customer, item.customer_id)
    if product.code != product_code:
        raise DomainError("WRONG_PRODUCT", "Lisensi bukan untuk produk ini.", 403)
    if product.status != "ACTIVE" or customer.status != "ACTIVE":
        raise DomainError("ACCOUNT_SUSPENDED", "Produk atau pelanggan dinonaktifkan.", 403)
    return product


def entitlement(item):
    if item.status != "ACTIVE":
        messages = {"PENDING": "Lisensi belum diaktifkan.", "EXPIRED": "Lisensi telah kedaluwarsa. Silakan perpanjang.",
                    "REVOKED": "Lisensi telah dicabut oleh administrator.", "SUSPENDED": "Lisensi sedang ditangguhkan. Hubungi administrator."}
        raise DomainError("LICENSE_" + item.status, messages[item.status], 403)


def generate(db, data, actor, settings):
    plan = db.get(Plan, data.plan_id)
    customer = db.get(Customer, data.customer_id)
    product = db.get(Product, data.product_id)
    if (not plan or plan.product_id != data.product_id or not plan.is_active or
            not customer or customer.status != "ACTIVE" or not product or product.status != "ACTIVE"):
        raise DomainError("INVALID_PLAN", "Pelanggan, produk, atau paket tidak tersedia.")
    key = new_key()
    item = License(**data.model_dump(), key_hash=digest(key, settings.key_pepper), key_prefix=key[:12],
                   duration_seconds=plan.duration_seconds, max_devices=plan.max_devices)
    db.add(item); db.flush()
    audit(db, "license.created", item, actor, details={"price_idr": plan.price_idr})
    return item, key


def activate(db, data, settings, signer):
    now = utcnow()
    item = db.scalar(select(License).where(License.key_hash == digest(normalize_key(data.license_key), settings.key_pepper)).with_for_update())
    if not item:
        raise DomainError("INVALID_KEY", "Kunci lisensi tidak valid.", 403)
    product = eligible(db, item, data.product_code)
    expire(db, item, now)
    if item.status != "PENDING":
        entitlement(item)
    activation = db.scalar(select(Activation).where(Activation.license_id == item.id,
        Activation.device_hash == data.device_hash, Activation.deactivated_at.is_(None)))
    secret = None
    if activation:
        if not data.activation_secret or not secrets.compare_digest(activation.secret_hash, digest(data.activation_secret, settings.key_pepper)):
            raise DomainError("DEVICE_ALREADY_REGISTERED", "Perangkat terdaftar. Pulihkan cache atau hubungi admin untuk reset.", 409)
    else:
        count = db.scalar(select(func.count()).select_from(Activation).where(Activation.license_id == item.id, Activation.deactivated_at.is_(None)))
        if count >= item.max_devices:
            raise DomainError("DEVICE_LIMIT", "Batas perangkat tercapai. Hubungi admin untuk reset.", 409)
        secret = secrets.token_urlsafe(48)
        activation = Activation(license_id=item.id, device_hash=data.device_hash,
                                secret_hash=digest(secret, settings.key_pepper), activated_at=now, last_seen_at=now)
        db.add(activation); db.flush()
        audit(db, "device.activated", activation, str(item.id), "desktop", {"license_id": str(item.id)})
    if item.status == "PENDING":
        item.activated_at = now
        item.expires_at = now + timedelta(seconds=item.duration_seconds)
        transition(db, item, "ACTIVE", str(item.id), "desktop")
    activation.last_seen_at = now
    result = signer.issue(item, activation, product, now)
    if secret:
        result["activation_secret"] = secret
    return result


def authenticated_device(db, secret, data, settings):
    found = db.scalar(select(Activation).where(Activation.secret_hash == digest(secret, settings.key_pepper)))
    if not found:
        raise DomainError("INVALID_DEVICE_CREDENTIAL", "Kredensial perangkat tidak valid.", 401)
    item = locked_license(db, found.license_id)
    # Refresh setelah penguncian: reset admin mungkin selesai sewaktu menunggu.
    db.refresh(found)
    if found.deactivated_at is not None or found.device_hash != data.device_hash:
        raise DomainError("DEVICE_DEACTIVATED", "Perangkat tidak terdaftar atau telah direset.", 403)
    product = eligible(db, item, data.product_code)
    return item, found, product


def validate(db, secret, data, settings, signer, deactivate=False):
    item, activation, product = authenticated_device(db, secret, data, settings)
    now = utcnow()
    expire(db, item, now)
    if deactivate:
        activation.deactivated_at = now
        audit(db, "device.deactivated", activation, str(item.id), "desktop", {"license_id": str(item.id)})
        return {"status": "DEACTIVATED", "server_time": now}
    entitlement(item)
    activation.last_seen_at = now
    return signer.issue(item, activation, product, now)


def renew(db, item, data, actor):
    prior = db.scalar(select(Renewal).where(Renewal.license_id == item.id, Renewal.idempotency_key == data.idempotency_key))
    if prior:
        audit_entry = db.scalar(select(AuditLog).where(AuditLog.resource_id == str(prior.id), AuditLog.action == "license.renewed"))
        if (not audit_entry or audit_entry.details.get("plan_id") != str(data.plan_id) or
                audit_entry.details.get("payment_reference") != data.payment_reference):
            raise DomainError("IDEMPOTENCY_CONFLICT", "Kunci idempotensi sudah dipakai untuk permintaan berbeda.", 409)
        return prior
    if item.status in ("REVOKED", "SUSPENDED", "PENDING"):
        raise DomainError("RENEWAL_NOT_ALLOWED", "Lisensi dicabut, ditangguhkan, atau belum diaktifkan; perpanjangan ditolak.", 409)
    plan = db.get(Plan, data.plan_id)
    if not plan or not plan.is_active or plan.product_id != item.product_id:
        raise DomainError("INVALID_PLAN", "Paket perpanjangan tidak tersedia.")
    now = utcnow()
    expire(db, item, now)
    previous = item.expires_at
    item.expires_at = max(previous, now) + timedelta(seconds=plan.duration_seconds)
    if item.status == "EXPIRED":
        transition(db, item, "ACTIVE", actor)
    renewal = Renewal(license_id=item.id, duration_seconds=plan.duration_seconds,
                      previous_expiry=previous, new_expiry=item.expires_at,
                      idempotency_key=data.idempotency_key, performed_by=actor)
    db.add(renewal); db.flush()
    audit(db, "license.renewed", renewal, actor, details={"license_id": str(item.id), "plan_id": str(plan.id),
          "payment_reference": data.payment_reference, "price_idr": plan.price_idr})
    return renewal

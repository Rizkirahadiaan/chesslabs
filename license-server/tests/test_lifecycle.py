from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, DatabaseError

from app.db import utcnow
from app.models import License, Activation, Renewal, AuditLog, Plan

BASE = "/api/v1/admin/licenses/"
DEVICE = {"product_code": "chesslab-pc", "device_hash": "a" * 64}


def activation(client, ids, **extra):
    return client.post("/api/v1/licenses/activate", json=dict(DEVICE, license_key=ids["license_key"], **extra))


def renewal(client, ids, idempotency="payment-unique-0001"):
    return client.post(BASE + ids["license"] + "/renew", json={"idempotency_key": idempotency,
        "plan_id": ids["plan"], "payment_reference": "transfer-bank-0001"})


def test_generation_hides_key_and_first_activation(issued):
    app, client, ids, _ = issued
    with app.state.sessions() as db:
        item = db.get(License, UUID(ids["license"]))
        assert item.status == "PENDING" and item.activated_at is None and item.expires_at is None
        assert item.key_hash != ids["license_key"] and len(item.key_hash) == 64
    before = utcnow()
    response = activation(client, ids)
    assert response.status_code == 200, response.text
    with app.state.sessions() as db:
        item = db.get(License, UUID(ids["license"]))
        assert item.status == "ACTIVE" and item.activated_at >= before
        assert item.expires_at - item.activated_at == timedelta(days=5)
    detail = client.get(BASE + ids["license"]).text
    assert ids["license_key"] not in detail and "key_hash" not in detail and "secret_hash" not in detail
    assert client.get("/healthz").status_code == 200


def test_renew_active_and_idempotency(issued):
    app, client, ids, _ = issued
    activation(client, ids)
    with app.state.sessions() as db: previous = db.get(License, UUID(ids["license"])).expires_at
    first = renewal(client, ids)
    second = renewal(client, ids)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    with app.state.sessions() as db:
        assert db.get(License, UUID(ids["license"])).expires_at == previous + timedelta(days=5)
        assert len(db.scalars(select(Renewal)).all()) == 1
        assert len(db.scalars(select(AuditLog).where(AuditLog.action == "license.renewed")).all()) == 1
    conflict = client.post(BASE + ids["license"] + "/renew", json={"idempotency_key": "payment-unique-0001", "plan_id": ids["plan"], "payment_reference": "different-payment"})
    assert conflict.status_code == 409


def test_renew_expired_from_confirmation(issued):
    app, client, ids, _ = issued
    activation(client, ids)
    with app.state.sessions.begin() as db:
        item = db.get(License, UUID(ids["license"]))
        item.activated_at = utcnow() - timedelta(days=6)
        item.expires_at = utcnow() - timedelta(days=1)
    now = utcnow()
    assert renewal(client, ids).status_code == 200
    with app.state.sessions() as db:
        item = db.get(License, UUID(ids["license"]))
        assert item.status == "ACTIVE" and now + timedelta(days=5) <= item.expires_at <= utcnow() + timedelta(days=5)


@pytest.mark.parametrize("operation,status", [("revoke", "REVOKED"), ("suspend", "SUSPENDED")])
def test_denied_state_rejects_validation_and_renewal(issued, operation, status):
    app, client, ids, _ = issued
    result = activation(client, ids).json()
    changed = client.post(BASE + ids["license"] + "/" + operation, json={"reason": "Permintaan pengelola"})
    assert changed.status_code == 200 and changed.json()["status"] == status
    assert renewal(client, ids).status_code == 409
    assert activation(client, ids).status_code == 403
    checked = client.post("/api/v1/licenses/validate", json=DEVICE, headers={"Authorization": "Bearer " + result["activation_secret"]})
    assert checked.status_code == 403 and checked.json()["error"]["code"] == "LICENSE_" + status


def test_device_limit_reset_and_deactivate(issued):
    app, client, ids, _ = issued
    first = activation(client, ids).json()
    assert activation(client, ids).status_code == 409
    assert activation(client, ids, activation_secret=first["activation_secret"]).status_code == 200
    other = dict(DEVICE, device_hash="b" * 64, license_key=ids["license_key"])
    assert client.post("/api/v1/licenses/activate", json=other).status_code == 409
    assert client.post(BASE + ids["license"] + "/devices/reset", json={"reason": "Pindah komputer pelanggan"}).status_code == 200
    assert client.post("/api/v1/licenses/validate", json=DEVICE, headers={"Authorization": "Bearer " + first["activation_secret"]}).status_code == 403
    second = client.post("/api/v1/licenses/activate", json=other)
    assert second.status_code == 200
    secret = second.json()["activation_secret"]
    assert client.post("/api/v1/licenses/deactivate", json=dict(DEVICE, device_hash="b" * 64), headers={"Authorization": "Bearer " + secret}).status_code == 200
    assert client.post("/api/v1/licenses/validate", json=dict(DEVICE, device_hash="b" * 64), headers={"Authorization": "Bearer " + secret}).status_code == 403


def test_invalid_key_product_and_device(issued):
    app, client, ids, _ = issued
    assert activation(client, dict(ids, license_key="CLP-" + "0"*40)).status_code == 403
    assert client.post("/api/v1/licenses/activate", json=dict(DEVICE, product_code="other-product", license_key=ids["license_key"])).status_code == 403
    result = activation(client, ids).json()
    assert client.post("/api/v1/licenses/validate", json=dict(DEVICE, device_hash="b"*64), headers={"Authorization": "Bearer " + result["activation_secret"]}).status_code == 403
    assert client.get("/api/v1/licenses/status", params=DEVICE, headers={"Authorization": "Bearer " + result["activation_secret"]}).status_code == 200


def test_immutable_history_and_database_constraints(issued):
    app, client, ids, _ = issued
    activation(client, ids); renewal(client, ids)
    for table in ("audit_logs", "license_renewals"):
        for action in ("UPDATE " + table + " SET id=id", "DELETE FROM " + table):
            with pytest.raises(DatabaseError), app.state.sessions.begin() as db: db.execute(text(action))
    with pytest.raises(IntegrityError), app.state.sessions.begin() as db:
        db.get(Plan, UUID(ids["plan"])).max_devices = 0
    with pytest.raises(IntegrityError), app.state.sessions.begin() as db:
        db.get(License, UUID(ids["license"])).status = "UNKNOWN"


def test_expiry_filter_and_plan_update_preserves_purchase(issued):
    app, client, ids, _ = issued
    plan = client.get("/api/v1/admin/plans").json()["items"][0]
    plan.pop("id"); plan["duration_seconds"] = 86400
    assert client.put("/api/v1/admin/plans/"+ids["plan"], json=plan).status_code == 200
    assert activation(client, ids).status_code == 200
    with app.state.sessions.begin() as db:
        item = db.get(License, UUID(ids["license"]))
        assert item.expires_at-item.activated_at == timedelta(days=5)
        item.activated_at = utcnow()-timedelta(days=6); item.expires_at = utcnow()-timedelta(seconds=1)
    assert client.get("/api/v1/admin/licenses?status=EXPIRED").json()["total"] == 1
    assert client.get("/api/v1/admin/dashboard/summary").json()["counts"]["EXPIRED"] == 1
    assert activation(client, ids).json()["error"]["code"] == "LICENSE_EXPIRED"

from datetime import timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, Query
from sqlalchemy import select, func, or_

from . import schemas as S
from . import services as service
from .auth import db_session, admin_user, operator, owner, login, rate_limit, ip
from .core.security import digest
from .db import utcnow
from .models import Customer, Product, Plan, License, Activation, Renewal, AuditLog
from .repositories import locked_license, list_rows

router = APIRouter(prefix="/api/v1")
DB = Annotated[object, Depends(db_session)]
Admin = Annotated[object, Depends(admin_user)]
Operator = Annotated[object, Depends(operator)]
Owner = Annotated[object, Depends(owner)]
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


def record(item):
    excluded = {"key_hash", "secret_hash", "password_hash", "token_hash", "csrf_hash"}
    result = {c.key: getattr(item, c.key) for c in item.__mapper__.column_attrs if c.key not in excluded}
    if isinstance(item, License):
        result["status"] = service.effective_status(item)
    return result


def collection(result):
    return dict(result, items=[record(row) for row in result["items"]])


def find(db, model, id):
    item = db.get(model, id)
    if not item:
        raise service.DomainError("NOT_FOUND", "Data tidak ditemukan.", 404)
    return item


def find_license(db, id):
    item = locked_license(db, id)
    if not item:
        raise service.DomainError("NOT_FOUND", "Lisensi tidak ditemukan.", 404)
    service.expire(db, item, utcnow())
    return item


def bearer(request):
    value = request.headers.get("authorization", "")
    if not value.startswith("Bearer ") or not 32 <= len(value[7:]) <= 128:
        raise service.DomainError("UNAUTHORIZED", "Kredensial perangkat diperlukan.", 401)
    return value[7:]


@router.post("/licenses/activate")
def activate(data: S.ActivateInput, request: Request, db: DB):
    rate_limit(request, "activation", ip(request), request.app.state.settings.activation_limit, 900)
    return service.activate(db, data, request.app.state.settings, request.app.state.signer)


def desktop_validate(data, request, db, deactivate=False):
    secret = bearer(request)
    rate_limit(request, "validation-ip", ip(request), request.app.state.settings.validation_limit)
    rate_limit(request, "validation-device", digest(secret), 20)
    return service.validate(db, secret, data, request.app.state.settings, request.app.state.signer, deactivate)


@router.post("/licenses/validate")
def validate(data: S.DeviceInput, request: Request, db: DB):
    return desktop_validate(data, request, db)


@router.get("/licenses/status")
def status(request: Request, db: DB, product_code: str, device_hash: str):
    return desktop_validate(S.DeviceInput(product_code=product_code, device_hash=device_hash), request, db)


@router.post("/licenses/deactivate")
def deactivate(data: S.DeviceInput, request: Request, db: DB):
    return desktop_validate(data, request, db, True)


@router.post("/admin/auth/login")
def admin_login(data: S.Login, request: Request, response: Response, db: DB):
    return login(request, response, data, db)


@router.get("/admin/auth/me")
def me(admin: Admin):
    return {"email": admin.email, "role": admin.role}


@router.post("/admin/auth/logout")
def logout(request: Request, response: Response, db: DB, admin: Admin):
    db.delete(request.state.admin_session)
    service.audit(db, "admin.logout", admin, admin.id)
    response.delete_cookie("chesslab_session", path="/")
    response.delete_cookie("chesslab_csrf", path="/")
    return {"message": "Anda telah keluar."}


@router.get("/admin/dashboard/summary")
def summary(db: DB, admin: Admin):
    now = utcnow()
    grouped = dict(db.execute(select(License.status, func.count()).group_by(License.status)).all())
    overdue = db.scalar(select(func.count()).select_from(License).where(License.status == "ACTIVE", License.expires_at <= now))
    grouped["ACTIVE"] = grouped.get("ACTIVE", 0) - overdue
    grouped["EXPIRED"] = grouped.get("EXPIRED", 0) + overdue
    soon = db.scalar(select(func.count()).select_from(License).where(License.status == "ACTIVE", License.expires_at > now, License.expires_at <= now+timedelta(days=1)))
    return {"total": sum(grouped.values()), "counts": grouped, "expiring_soon": soon,
            "recent_activations": [record(r) for r in db.scalars(select(Activation).order_by(Activation.activated_at.desc()).limit(10))],
            "recent_renewals": [record(r) for r in db.scalars(select(Renewal).order_by(Renewal.created_at.desc()).limit(10))]}


@router.get("/admin/customers")
def customers(db: DB, admin: Admin, page: Page = 1, size: Size = 25, q: str = Query(default="", max_length=200)):
    return collection(list_rows(db, Customer, page, size, conditions=[or_(Customer.name.ilike(f"%{q}%"), Customer.email.ilike(f"%{q}%"))]))


@router.post("/admin/customers", status_code=201)
def create_customer(data: S.CustomerInput, db: DB, admin: Operator):
    item = Customer(**data.model_dump()); item.email = item.email.lower()
    db.add(item); db.flush(); service.audit(db, "customer.created", item, admin.id)
    return record(item)


@router.patch("/admin/customers/{id}")
def update_customer(id: UUID, data: S.CustomerInput, db: DB, admin: Owner):
    item = find(db, Customer, id)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    item.email = item.email.lower()
    service.audit(db, "customer.updated", item, admin.id)
    return record(item)


@router.get("/admin/products")
def products(db: DB, admin: Admin, page: Page = 1, size: Size = 100):
    return collection(list_rows(db, Product, page, size, "name"))


@router.post("/admin/products", status_code=201)
def create_product(data: S.ProductInput, db: DB, admin: Owner):
    item = Product(**data.model_dump()); db.add(item); db.flush()
    service.audit(db, "product.created", item, admin.id)
    return record(item)


@router.get("/admin/plans")
def plans(db: DB, admin: Admin, page: Page = 1, size: Size = 100):
    return collection(list_rows(db, Plan, page, size, "name"))


@router.post("/admin/plans", status_code=201)
def create_plan(data: S.PlanInput, db: DB, admin: Owner):
    find(db, Product, data.product_id)
    item = Plan(**data.model_dump()); db.add(item); db.flush()
    service.audit(db, "plan.created", item, admin.id)
    return record(item)


@router.put("/admin/plans/{id}")
def update_plan(id: UUID, data: S.PlanInput, db: DB, admin: Owner):
    item = find(db, Plan, id)
    if item.product_id != data.product_id:
        raise service.DomainError("INVALID_PRODUCT", "Produk paket tidak dapat diganti.", 409)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    service.audit(db, "plan.updated", item, admin.id)
    return record(item)


@router.get("/admin/licenses")
def licenses(db: DB, admin: Admin, page: Page = 1, size: Size = 25,
             status: Literal["PENDING", "ACTIVE", "EXPIRED", "REVOKED", "SUSPENDED"] | None = None,
             q: str = Query(default="", max_length=100),
             sort: Literal["created_at", "expires_at", "key_prefix"] = "created_at",
             order: Literal["asc", "desc"] = "desc"):
    conditions = [License.key_prefix.ilike(f"%{q}%")]
    if status == "EXPIRED":
        conditions.append(or_(License.status == "EXPIRED", (License.status == "ACTIVE") & (License.expires_at <= utcnow())))
    elif status == "ACTIVE":
        conditions.extend([License.status == "ACTIVE", License.expires_at > utcnow()])
    elif status:
        conditions.append(License.status == status)
    return collection(list_rows(db, License, page, size, sort, order == "desc", conditions))


@router.post("/admin/licenses", status_code=201)
def create_license(data: S.LicenseInput, request: Request, db: DB, admin: Operator):
    item, key = service.generate(db, data, admin.id, request.app.state.settings)
    return {"license": record(item), "license_key": key,
            "message": "Salin dan simpan kunci sekarang. Kunci lengkap tidak dapat ditampilkan kembali."}


@router.get("/admin/licenses/{id}")
def license_detail(id: UUID, db: DB, admin: Admin):
    item = find_license(db, id)
    return {"license": record(item), "customer": record(db.get(Customer, item.customer_id)),
            "plan": record(item.plan), "renewals": [record(r) for r in db.scalars(select(Renewal).where(Renewal.license_id == id).order_by(Renewal.created_at.desc()))],
            "activations": [record(r) for r in db.scalars(select(Activation).where(Activation.license_id == id).order_by(Activation.activated_at.desc()))]}


@router.post("/admin/licenses/{id}/renew")
def renew(id: UUID, data: S.RenewInput, db: DB, admin: Operator):
    return record(service.renew(db, find_license(db, id), data, admin.id))


def change_state(db, id, data, admin, state):
    item = find_license(db, id)
    service.transition(db, item, state, admin.id, details={"reason": data.reason})
    if state == "REVOKED": item.revoked_at = utcnow()
    return record(item)


@router.post("/admin/licenses/{id}/revoke")
def revoke(id: UUID, data: S.ReasonInput, db: DB, admin: Owner):
    return change_state(db, id, data, admin, "REVOKED")


@router.post("/admin/licenses/{id}/suspend")
def suspend(id: UUID, data: S.ReasonInput, db: DB, admin: Owner):
    return change_state(db, id, data, admin, "SUSPENDED")


@router.get("/admin/licenses/{id}/devices")
def devices(id: UUID, db: DB, admin: Admin, page: Page = 1, size: Size = 25):
    find(db, License, id)
    return collection(list_rows(db, Activation, page, size, "activated_at", conditions=[Activation.license_id == id]))


@router.post("/admin/licenses/{id}/devices/reset")
def reset(id: UUID, data: S.ReasonInput, db: DB, admin: Owner):
    item = find_license(db, id)
    for activation in db.scalars(select(Activation).where(Activation.license_id == id, Activation.deactivated_at.is_(None))):
        activation.deactivated_at = utcnow()
    service.audit(db, "device.reset", item, admin.id, details={"reason": data.reason})
    return {"message": "Perangkat direset. Grant offline lama berlaku paling lama sampai batas grant."}


@router.get("/admin/audit-logs")
def audit_logs(db: DB, admin: Admin, page: Page = 1, size: Size = 25,
               resource_id: str | None = Query(default=None, max_length=64),
               action: str | None = Query(default=None, max_length=64)):
    conditions = []
    if resource_id: conditions.append(or_(AuditLog.resource_id == resource_id, AuditLog.details["license_id"].as_string() == resource_id))
    if action: conditions.append(AuditLog.action == action)
    return collection(list_rows(db, AuditLog, page, size, conditions=conditions))

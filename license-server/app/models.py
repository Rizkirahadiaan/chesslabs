import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, ForeignKeyConstraint, CheckConstraint, UniqueConstraint, Index, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, UTCDateTime, utcnow


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Customer(Identity, Timestamps, Base):
    __tablename__ = "customers"
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    __table_args__ = (CheckConstraint("status IN ('ACTIVE', 'SUSPENDED')", name="customer_status"),)


class Product(Identity, Base):
    __tablename__ = "products"
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    __table_args__ = (CheckConstraint("status IN ('ACTIVE', 'SUSPENDED')", name="product_status"),)


class Plan(Identity, Base):
    __tablename__ = "license_plans"
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    duration_seconds: Mapped[int]
    price_idr: Mapped[int]
    max_devices: Mapped[int]
    is_active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (CheckConstraint("duration_seconds > 0 AND price_idr >= 0 AND max_devices > 0", name="plan_bounds"),
                      UniqueConstraint("id", "product_id", name="plan_product_unique"))


class License(Identity, Timestamps, Base):
    __tablename__ = "licenses"
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Snapshot ketentuan pembelian; perubahan paket berlaku untuk pembelian berikutnya.
    duration_seconds: Mapped[int]
    max_devices: Mapped[int]
    plan: Mapped[Plan] = relationship()
    __table_args__ = (ForeignKeyConstraint(["plan_id", "product_id"], ["license_plans.id", "license_plans.product_id"], name="license_plan_product"),
                      CheckConstraint("status IN ('PENDING','ACTIVE','EXPIRED','REVOKED','SUSPENDED')", name="license_status"),
                      CheckConstraint("duration_seconds > 0 AND max_devices > 0", name="license_bounds"),
                      CheckConstraint("(activated_at IS NULL AND expires_at IS NULL) OR (activated_at IS NOT NULL AND expires_at > activated_at)", name="license_dates"),
                      CheckConstraint("status != 'ACTIVE' OR activated_at IS NOT NULL", name="active_has_dates"))


class Activation(Identity, Base):
    __tablename__ = "device_activations"
    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id"), index=True)
    device_hash: Mapped[str] = mapped_column(String(64))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    activated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    deactivated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    __table_args__ = (Index("one_live_device", "license_id", "device_hash", unique=True,
                          postgresql_where=deactivated_at.is_(None), sqlite_where=deactivated_at.is_(None)),)


class Administrator(Identity, Base):
    __tablename__ = "administrators"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(16), default="admin")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (CheckConstraint("role IN ('admin','operator','viewer')", name="admin_role"),
                      CheckConstraint("status IN ('ACTIVE','SUSPENDED')", name="admin_status"))


class AdminSession(Identity, Base):
    __tablename__ = "admin_sessions"
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("administrators.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


class Renewal(Identity, Base):
    __tablename__ = "license_renewals"
    license_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("licenses.id"), index=True)
    duration_seconds: Mapped[int]
    previous_expiry: Mapped[datetime | None] = mapped_column(UTCDateTime)
    new_expiry: Mapped[datetime] = mapped_column(UTCDateTime)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    performed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("administrators.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("license_id", "idempotency_key", name="renewal_once"),
                      CheckConstraint("duration_seconds > 0", name="renewal_duration"))


class AuditLog(Identity, Base):
    __tablename__ = "audit_logs"
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(primary_key=True)
    hits: Mapped[int] = mapped_column(default=1)

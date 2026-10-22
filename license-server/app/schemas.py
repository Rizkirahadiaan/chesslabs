from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, EmailStr


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class CustomerInput(Input):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|SUSPENDED)$")


class ProductInput(Input):
    code: str = Field(pattern="^[a-z0-9-]{2,64}$")
    name: str = Field(min_length=1, max_length=120)
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|SUSPENDED)$")


class PlanInput(Input):
    product_id: UUID
    name: str = Field(min_length=1, max_length=120)
    duration_seconds: int = Field(gt=0, le=315360000)
    price_idr: int = Field(ge=0, le=2000000000)
    max_devices: int = Field(gt=0, le=1000)
    is_active: bool = True


class LicenseInput(Input):
    customer_id: UUID
    product_id: UUID
    plan_id: UUID


class DeviceInput(Input):
    product_code: str = Field(pattern="^[a-z0-9-]{2,64}$")
    device_hash: str = Field(pattern="^[0-9a-f]{64}$")


class ActivateInput(DeviceInput):
    license_key: str = Field(min_length=20, max_length=100)
    activation_secret: str | None = Field(default=None, max_length=128)


class RenewInput(Input):
    idempotency_key: str = Field(min_length=16, max_length=128)
    plan_id: UUID
    payment_reference: str = Field(min_length=3, max_length=200)


class ReasonInput(Input):
    reason: str = Field(min_length=5, max_length=500)

import sys
import os
from uuid import uuid4
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import Settings
from app.core.security import password_hasher
from app.main import create_app
from app.models import Administrator, Product, Plan


@pytest.fixture
def platform(tmp_path):
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "test-key.pem"
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    url = os.environ.get("CHESSLAB_TEST_DATABASE_URL", "sqlite:///" + str(tmp_path / "test.db"))
    schema = None
    if url.startswith("postgresql"):
        parsed = make_url(url)
        if not parsed.database.endswith("_test"):
            raise RuntimeError("Uji PostgreSQL hanya boleh memakai database dengan nama berakhiran _test.")
        schema = "license_test_" + uuid4().hex
        admin_engine = create_engine(url, hide_parameters=True)
        with admin_engine.begin() as connection: connection.execute(text('CREATE SCHEMA "' + schema + '"'))
        url = parsed.update_query_dict({"options": "-csearch_path="+schema}).render_as_string(hide_password=False)
    settings = Settings(database_url=url, key_pepper="test-only-pepper-" * 3,
                        signing_key_path=private, public_origin="http://testserver", secure_cookies=False, testing=True)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["database_url"] = settings.database_url
    command.upgrade(config, "head")
    app = create_app(settings)
    with app.state.sessions.begin() as db:
        admin = Administrator(email="admin@example.com", password_hash=password_hasher.hash("test-only-password-123"))
        product = Product(code="chesslab-pc", name="ChessLab PC")
        db.add_all([admin, product]); db.flush()
        plan = Plan(product_id=product.id, name="ChessLab Pro", duration_seconds=432000, price_idr=50000, max_devices=1)
        db.add(plan); db.flush()
        ids = {"admin": str(admin.id), "product": str(product.id), "plan": str(plan.id)}
    with TestClient(app) as client:
        yield app, client, ids, key
    if schema:
        with admin_engine.begin() as connection: connection.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def admin(platform):
    app, client, ids, key = platform
    response = client.post("/api/v1/admin/auth/login", json={"email": "admin@example.com", "password": "test-only-password-123"},
                           headers={"Origin": "http://testserver"})
    assert response.status_code == 200, response.text
    client.headers.update({"Origin": "http://testserver", "X-CSRF-Token": client.cookies["chesslab_csrf"]})
    return app, client, ids, key


@pytest.fixture
def issued(admin):
    app, client, ids, key = admin
    customer = client.post("/api/v1/admin/customers", json={"name": "Pelanggan Uji", "email": "customer@example.com"})
    assert customer.status_code == 201, customer.text
    result = client.post("/api/v1/admin/licenses", json={"customer_id": customer.json()["id"], "product_id": ids["product"], "plan_id": ids["plan"]})
    assert result.status_code == 201, result.text
    return app, client, dict(ids, license=result.json()["license"]["id"], license_key=result.json()["license_key"]), key

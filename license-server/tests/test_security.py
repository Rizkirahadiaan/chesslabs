from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from app.db import utcnow
from app.models import Administrator, AdminSession


def test_admin_auth_csrf_session_and_logout(platform):
    app, client, ids, _ = platform
    assert client.get("/api/v1/admin/licenses").status_code == 401
    assert client.post("/api/v1/admin/auth/login", json={"email": "admin@example.com", "password": "test-only-password-123"}).status_code == 403
    response = client.post("/api/v1/admin/auth/login", json={"email": "admin@example.com", "password": "test-only-password-123"}, headers={"Origin": "http://testserver"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert "SameSite=strict" in response.headers.get_list("set-cookie")[0]
    assert client.post("/api/v1/admin/customers", json={"name": "X", "email": "x@example.com"}).status_code == 403
    csrf = {"Origin": "http://testserver", "X-CSRF-Token": client.cookies["chesslab_csrf"]}
    assert client.post("/api/v1/admin/auth/logout", headers=csrf).status_code == 200
    assert client.get("/api/v1/admin/licenses").status_code == 401


def test_session_expiration(admin):
    app, client, ids, _ = admin
    with app.state.sessions.begin() as db:
        db.scalar(select(AdminSession)).expires_at = utcnow()-timedelta(seconds=1)
    assert client.get("/api/v1/admin/licenses").status_code == 401


def test_role_and_device_reset_authorization(issued):
    app, client, ids, _ = issued
    with app.state.sessions.begin() as db: db.get(Administrator, UUID(ids["admin"])).role = "viewer"
    assert client.get("/api/v1/admin/licenses").status_code == 200
    assert client.post("/api/v1/admin/licenses/"+ids["license"]+"/devices/reset", json={"reason": "Uji reset tanpa hak"}).status_code == 403
    assert client.post("/api/v1/admin/customers", json={"name": "X", "email": "x@example.com"}).status_code == 403
    client.cookies.clear()
    assert client.post("/api/v1/admin/licenses/"+ids["license"]+"/devices/reset", headers={"Authorization": "Bearer "+ids["license_key"]}, json={"reason": "Uji tanpa sesi admin"}).status_code == 401


def test_rate_limit_activation_and_login(platform):
    app, client, ids, _ = platform
    app.state.settings.activation_limit = 2
    body = {"product_code": "chesslab-pc", "device_hash": "a"*64, "license_key": "CLP-"+"0"*40}
    assert client.post("/api/v1/licenses/activate", json=body).status_code == 403
    assert client.post("/api/v1/licenses/activate", json=body).status_code == 403
    assert client.post("/api/v1/licenses/activate", json=body).status_code == 429
    app.state.settings.login_limit = 1
    login = {"email": "unknown@example.com", "password": "wrong-password"}
    assert client.post("/api/v1/admin/auth/login", json=login, headers={"Origin": "http://testserver"}).status_code == 401
    assert client.post("/api/v1/admin/auth/login", json=login, headers={"Origin": "http://testserver"}).status_code == 429


def test_validation_response_does_not_echo_secret(platform):
    _, client, _, _ = platform
    response = client.post("/api/v1/admin/auth/login", json={"email": "invalid", "password": "secret-must-not-echo"})
    assert response.status_code == 422 and "secret-must-not-echo" not in response.text
    assert client.get("/openapi.json").status_code == 200

import secrets
import time
from datetime import timedelta

from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, Request, Response
from sqlalchemy import select

from .core.security import digest, password_hasher, dummy_hash
from .db import utcnow
from .models import Administrator, AdminSession, RateBucket
from .services import DomainError, audit


def db_session(request: Request):
    with request.app.state.sessions() as db:
        with db.begin():
            yield db


def rate_limit(request, scope, identity, limit, seconds=60):
    settings = request.app.state.settings
    window = (int(time.time()) // seconds) * seconds
    key = digest(scope + ":" + identity, settings.key_pepper)
    with request.app.state.sessions.begin() as db:
        if db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement = insert(RateBucket).values(key=key, window=window, hits=1)
        statement = statement.on_conflict_do_update(index_elements=[RateBucket.key, RateBucket.window],
                         set_={"hits": RateBucket.hits + 1}).returning(RateBucket.hits)
        hits = db.scalar(statement)
    if hits > limit:
        raise DomainError("RATE_LIMITED", "Terlalu banyak permintaan. Coba lagi nanti.", 429)


def ip(request):
    from ipaddress import ip_address, ip_network
    peer = request.client.host if request.client else "unknown"
    try:
        if any(ip_address(peer) in ip_network(cidr) for cidr in request.app.state.settings.trusted_proxy_cidrs):
            # Caddy menimpa header ini dengan satu alamat pemanggil.
            return str(ip_address(request.headers.get("x-forwarded-for", "")))
    except ValueError:
        pass
    return peer


def require_origin(request):
    if request.headers.get("origin") != request.app.state.settings.public_origin.rstrip("/"):
        raise DomainError("CSRF_FAILED", "Origin permintaan tidak diizinkan.", 403)


def admin_user(request: Request, db=Depends(db_session)):
    token = request.cookies.get("chesslab_session", "")
    session = db.scalar(select(AdminSession).where(AdminSession.token_hash == digest(token))) if token else None
    admin = db.get(Administrator, session.admin_id) if session else None
    if not session or session.expires_at <= utcnow() or not admin or admin.status != "ACTIVE":
        raise DomainError("UNAUTHORIZED", "Silakan masuk sebagai administrator.", 401)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not secrets.compare_digest(session.csrf_hash, digest(csrf)):
            raise DomainError("CSRF_FAILED", "Token keamanan tidak valid. Muat ulang halaman.", 403)
    request.state.admin_session = session
    return admin


def operator(admin=Depends(admin_user)):
    if admin.role not in ("admin", "operator"):
        raise DomainError("FORBIDDEN", "Peran Anda tidak mengizinkan perubahan ini.", 403)
    return admin


def owner(admin=Depends(admin_user)):
    if admin.role != "admin":
        raise DomainError("FORBIDDEN", "Tindakan ini membutuhkan peran admin.", 403)
    return admin


def login(request, response, data, db):
    require_origin(request)
    rate_limit(request, "login-ip", ip(request), request.app.state.settings.login_limit, 900)
    rate_limit(request, "login-account", data.email.lower(), request.app.state.settings.login_limit, 900)
    admin = db.scalar(select(Administrator).where(Administrator.email == data.email.lower()))
    valid = False
    try:
        valid = password_hasher.verify(admin.password_hash if admin else dummy_hash, data.password)
    except (VerificationError, InvalidHashError):
        pass
    if not valid or not admin or admin.status != "ACTIVE":
        raise DomainError("INVALID_CREDENTIALS", "Email atau kata sandi salah.", 401)
    if password_hasher.check_needs_rehash(admin.password_hash):
        admin.password_hash = password_hasher.hash(data.password)
    settings = request.app.state.settings
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    previous = request.cookies.get("chesslab_session")
    if previous:
        old = db.scalar(select(AdminSession).where(AdminSession.token_hash == digest(previous)))
        if old:
            db.delete(old)
    session = AdminSession(admin_id=admin.id, token_hash=digest(token), csrf_hash=digest(csrf),
                           expires_at=utcnow() + timedelta(seconds=settings.session_seconds))
    db.add(session)
    audit(db, "admin.login", admin, admin.id)
    options = dict(secure=settings.secure_cookies, samesite="strict", path="/", max_age=settings.session_seconds)
    response.set_cookie("chesslab_session", token, httponly=True, **options)
    response.set_cookie("chesslab_csrf", csrf, httponly=False, **options)
    return {"email": admin.email, "role": admin.role}

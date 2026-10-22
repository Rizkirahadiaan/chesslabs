from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.models import Activation, Renewal


@pytest.mark.postgres
def test_parallel_activation_cannot_exceed_device_limit(issued):
    app, _, ids, _ = issued
    if app.state.engine.dialect.name != "postgresql":pytest.skip("Membutuhkan PostgreSQL sungguhan")
    barrier=Barrier(8)
    def activate(index):
        client=TestClient(app)
        barrier.wait()
        return client.post("/api/v1/licenses/activate", json={"product_code":"chesslab-pc", "device_hash":f"{index:064x}","license_key":ids["license_key"]}).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(activate,range(8)))
    assert results.count(200)==1 and results.count(409)==7,results
    with app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Activation).where(Activation.license_id==UUID(ids["license"]),Activation.deactivated_at.is_(None)))==1


@pytest.mark.postgres
def test_parallel_renewal_is_idempotent(issued):
    app, client, ids, _ = issued
    if app.state.engine.dialect.name != "postgresql":pytest.skip("Membutuhkan PostgreSQL sungguhan")
    result=client.post("/api/v1/licenses/activate",json={"product_code":"chesslab-pc","device_hash":"a"*64,"license_key":ids["license_key"]})
    assert result.status_code==200
    cookies=dict(client.cookies);headers=dict(client.headers);barrier=Barrier(6)
    def renew(index):
        worker=TestClient(app,cookies=cookies,headers=headers)
        barrier.wait()
        return worker.post("/api/v1/admin/licenses/"+ids["license"]+"/renew",json={"plan_id":ids["plan"],"payment_reference":"bank-concurrent-0001","idempotency_key":"parallel-payment-0001"})
    with ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(renew,range(6)))
    assert all(r.status_code==200 for r in results),[(r.status_code,r.text) for r in results]
    assert len({r.json()["id"] for r in results})==1
    with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(Renewal))==1

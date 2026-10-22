from types import SimpleNamespace
from app.auth import ip


def test_forwarded_ip_only_from_trusted_proxy():
    settings=SimpleNamespace(trusted_proxy_cidrs=["172.16.0.0/12"])
    request=SimpleNamespace(client=SimpleNamespace(host="203.0.113.8"),headers={"x-forwarded-for":"198.51.100.5"},app=SimpleNamespace(state=SimpleNamespace(settings=settings)))
    assert ip(request)=="203.0.113.8"
    request.client.host="172.19.0.10"
    assert ip(request)=="198.51.100.5"
    request.headers["x-forwarded-for"]="198.51.100.5, 192.0.2.1"
    assert ip(request)=="172.19.0.10"

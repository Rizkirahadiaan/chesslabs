import json
from urllib.parse import urlsplit

import httpx


class LicenseAPIError(Exception):
    def __init__(self, message, code="NETWORK_ERROR", authoritative=False):
        super().__init__(message)
        self.code, self.authoritative = code, authoritative


class LicenseAPIClient:
    def __init__(self, base_url, product, device, transport=None):
        url = urlsplit(base_url)
        if (url.scheme != "https" and not (url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1"))) or url.username or url.password or url.query or url.fragment:
            raise ValueError("API lisensi membutuhkan HTTPS; HTTP hanya untuk localhost.")
        self.base_url, self.product, self.device = base_url.rstrip("/"), product, device
        self.transport = transport

    def call(self, operation, secret=None, license_key=None):
        body = {"product_code": self.product, "device_hash": self.device}
        if license_key:
            body["license_key"] = license_key.strip()
            if secret: body["activation_secret"] = secret
        headers = {"Authorization": "Bearer " + secret} if secret and not license_key else {}
        try:
            with httpx.Client(timeout=httpx.Timeout(10, connect=4), follow_redirects=False,
                              transport=self.transport, trust_env=False) as client:
                response = client.post(self.base_url + "/api/v1/licenses/" + operation, json=body, headers=headers)
            if response.status_code >= 500 or response.status_code == 429:
                raise LicenseAPIError("Server sibuk atau belum tersedia. Akan dicoba kembali.")
            if response.status_code != 200:
                error = response.json().get("error", {})
                code = error.get("code", "REQUEST_REJECTED")
                raise LicenseAPIError(error.get("message", "Permintaan lisensi ditolak."), code,
                                      authoritative=code in {"LICENSE_EXPIRED", "LICENSE_REVOKED", "LICENSE_SUSPENDED",
                                          "DEVICE_DEACTIVATED", "INVALID_DEVICE_CREDENTIAL", "ACCOUNT_SUSPENDED", "WRONG_PRODUCT"})
            if len(response.content) > 32768:
                raise ValueError()
            return response.json()
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            raise LicenseAPIError("Tidak dapat menghubungi server lisensi. Periksa koneksi lalu coba kembali.") from exc

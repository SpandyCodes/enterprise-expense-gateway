"""
Internal service-to-service endpoint protected by mutual TLS.

In this local architecture, Nginx terminates TLS and performs client
certificate verification (ssl_verify_client on), then forwards the
verified client certificate's Common Name (CN) to the app via the
X-Client-Cert-CN header (Nginx only sets this after a successful
verification and strips any client-supplied value first). The app
rejects requests missing that header — i.e. requests that did not pass
through Nginx's mTLS termination.

This endpoint is intentionally separate from the OAuth2 bearer-token API:
mTLS authenticates the *calling service/machine* at the transport layer,
while OAuth2 authenticates the *acting principal* at the application
layer. See docs/security.md for the mTLS vs OAuth2 discussion.
"""
from fastapi import APIRouter, Header, Request

from app.core.errors import api_error

router = APIRouter(tags=["internal"])


@router.post("/internal/integrations/expense-sync")
async def expense_sync(
    request: Request,
    x_client_cert_cn: str | None = Header(default=None, alias="X-Client-Cert-CN"),
):
    if not x_client_cert_cn:
        raise api_error(
            401,
            "MTLS_CLIENT_CERT_REQUIRED",
            "A verified client certificate is required for this endpoint",
        )
    body = await request.json()
    return {
        "status": "ACCEPTED",
        "verified_client": x_client_cert_cn,
        "received_keys": list(body.keys()),
    }

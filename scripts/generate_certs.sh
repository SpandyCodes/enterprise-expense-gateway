#!/usr/bin/env bash
# Generates a local development CA, server certificate, and client
# certificate for the mTLS internal integration endpoint.
#
# This is for LOCAL DEVELOPMENT / PORTFOLIO DEMONSTRATION ONLY.
# Never commit the generated .key files. See .gitignore.
set -euo pipefail

CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/certs"
DAYS=825

mkdir -p "$CERT_DIR/ca" "$CERT_DIR/server" "$CERT_DIR/client"
cd "$CERT_DIR"

echo "==> Generating local CA"
openssl genrsa -out ca/ca.key 4096
openssl req -x509 -new -nodes -key ca/ca.key -sha256 -days "$DAYS" \
  -out ca/ca.crt \
  -subj "/C=US/O=Expense Gateway Portfolio/OU=Local Dev CA/CN=expense-gateway-local-ca"

echo "==> Generating server certificate (for Nginx)"
openssl genrsa -out server/server.key 2048
openssl req -new -key server/server.key -out server/server.csr \
  -subj "/C=US/O=Expense Gateway Portfolio/OU=Server/CN=localhost"
cat > server/server.ext <<EOF
subjectAltName = DNS:localhost,DNS:nginx,IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
openssl x509 -req -in server/server.csr -CA ca/ca.crt -CAkey ca/ca.key \
  -CAcreateserial -out server/server.crt -days "$DAYS" -sha256 \
  -extfile server/server.ext

echo "==> Generating client certificate (for the integration caller)"
openssl genrsa -out client/client.key 2048
openssl req -new -key client/client.key -out client/client.csr \
  -subj "/C=US/O=Expense Gateway Portfolio/OU=Integration Client/CN=expense-integration-client"
cat > client/client.ext <<EOF
extendedKeyUsage = clientAuth
EOF
openssl x509 -req -in client/client.csr -CA ca/ca.crt -CAkey ca/ca.key \
  -CAcreateserial -out client/client.crt -days "$DAYS" -sha256 \
  -extfile client/client.ext

rm -f server/server.csr server/server.ext client/client.csr client/client.ext

echo "==> Done. Generated:"
echo "    certs/ca/ca.crt        (trust this to verify clients/server)"
echo "    certs/server/server.crt + server.key  (used by Nginx)"
echo "    certs/client/client.crt + client.key  (used by the integration caller)"
echo
echo "Example authenticated call once services are running:"
echo "  curl --cert certs/client/client.crt --key certs/client/client.key \\"
echo "       --cacert certs/ca/ca.crt \\"
echo "       https://localhost:8443/internal/integrations/expense-sync -d '{}'"

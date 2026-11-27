#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
umask 077
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

base='https://gu-st.ru/content/lending'
curl -fsSL --proto '=https' --proto-redir '=https' --max-time 30 \
  "$base/russian_trusted_root_ca_pem.crt" -o "$temp_dir/root.pem"
curl -fsSL --proto '=https' --proto-redir '=https' --max-time 30 \
  "$base/russian_trusted_sub_ca_pem.crt" -o "$temp_dir/sub.pem"

for name in root sub; do
  openssl x509 -in "$temp_dir/$name.pem" -noout -checkend 0 >/dev/null
  openssl x509 -in "$temp_dir/$name.pem" -noout -text | grep 'CA:TRUE' >/dev/null
done
openssl x509 -in "$temp_dir/root.pem" -noout -subject | grep -q 'CN *= *Russian Trusted Root CA'
openssl x509 -in "$temp_dir/sub.pem" -noout -subject | grep -q 'CN *= *Russian Trusted Sub CA'
openssl verify -CAfile "$temp_dir/root.pem" "$temp_dir/sub.pem" >/dev/null

{
  cat "$temp_dir/root.pem"
  printf '\n'
  cat "$temp_dir/sub.pem"
  printf '\n'
} > "$temp_dir/max-ca.pem"

".venv/bin/python" - "$temp_dir/max-ca.pem" <<'PY'
import ssl
import sys

import certifi
import httpx

context = ssl.create_default_context(cafile=certifi.where())
context.load_verify_locations(cafile=sys.argv[1])
response = httpx.get("https://platform-api2.max.ru/subscriptions", verify=context, timeout=15)
print(f"MAX TLS verified (HTTP {response.status_code} without a token)")
PY

mkdir -p runtime-data/certs
chmod 700 runtime-data/certs
mv "$temp_dir/max-ca.pem" runtime-data/certs/max-ca.pem
chmod 600 runtime-data/certs/max-ca.pem
echo 'Project-only MAX certificate installed. Restart this site: bash deploy-linux.sh restart'

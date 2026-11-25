#!/bin/bash
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

cat "$temp_dir/root.pem" "$temp_dir/sub.pem" > "$temp_dir/max-ca.pem"
mkdir -p runtime-data/certs
chmod 700 runtime-data/certs
mv "$temp_dir/max-ca.pem" runtime-data/certs/max-ca.pem
chmod 600 runtime-data/certs/max-ca.pem

status="$(curl -sS --cacert runtime-data/certs/max-ca.pem --max-time 15 \
  -o /dev/null -w '%{http_code}' https://platform-api2.max.ru/subscriptions)"
if [ "$status" != 401 ] && [ "$status" != 200 ]; then
  echo "TLS установлен, но API MAX ответил HTTP $status. Проверьте сеть." >&2
  exit 1
fi
echo "TLS MAX проверен (HTTP $status без токена). Перезапустите службу: bash scripts/site-service-mac.sh restart"

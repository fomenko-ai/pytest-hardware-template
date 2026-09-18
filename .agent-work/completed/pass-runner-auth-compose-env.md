# Pass runner authentication settings through Compose

## Result

The standalone runner Compose service now passes its API token, and the virtual-stand runner
service passes the complete browser and Bearer authentication configuration from `.env`.

## Verification

- Both Compose files passed `docker compose config --quiet`.
- `./scripts/ci.sh`: passed.

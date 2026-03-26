# swagger-merger

Dockerized utility to merge OpenAPI/Swagger specs from multiple services into one spec.

## What it does
- Reads a merge configuration (`YAML` or `JSON`).
- Pulls each service OpenAPI spec from either:
  - local file path, or
  - HTTP/HTTPS URL.
- Optionally prefixes paths per service (for gateway-style routing).
- Merges `paths`, `components`, `tags`, and `security` into one document.
- Fails fast on conflicting path/component definitions.

## Build image

```bash
docker build -t swagger-merger .
```

## Run with Docker

```bash
docker run --rm \
  -v "$(pwd)/config.example.yaml:/config/config.yaml:ro" \
  -v "$(pwd)/examples:/work/examples:ro" \
  -v "$(pwd)/out:/out" \
  -w /work \
  swagger-merger \
  --config /config/config.yaml \
  --output /out/merged-openapi.yaml
```

> Note: if your config uses local files in `source`, those files must be mounted inside the container and paths in config should match container paths.

## Configuration format

```yaml
openapi: 3.0.3
info:
  title: "Platform API"
  version: "2026.03"
servers:
  - url: https://api.example.com
http_timeout_seconds: 20
services:
  - name: users
    source: ./examples/users.yaml
    path_prefix: /users
  - name: billing
    source: https://billing.example.com/openapi.yaml
    path_prefix: /billing
```

### Fields
- `openapi` *(optional)*: output OpenAPI version. Default: `3.0.3`.
- `info` *(optional)*: output `info` object. Default title/version are set if omitted.
- `servers` *(optional)*: copied to output.
- `http_timeout_seconds` *(optional)*: timeout for URL sources. Default: `15`.
- `services` *(required list)*:
  - `name` *(optional)*: used in error messages.
  - `source` *(required)*: local path or URL to service spec.
  - `path_prefix` *(optional)*: prefix added to every path from that service.

## Local usage (without Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python merger.py --config config.example.yaml --output merged-openapi.yaml
```

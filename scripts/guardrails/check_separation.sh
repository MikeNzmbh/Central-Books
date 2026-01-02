#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

TARGETS=(backend apps)

fail() {
  echo "[guardrail] $1" >&2
  exit 1
}

if rg -n -i "django|allauth|manage\.py|SessionMiddleware|TemplateResponse|render_to_string" "${TARGETS[@]}"; then
  fail "Django references found outside legacy/"
fi

if rg -n "legacy/" "${TARGETS[@]}"; then
  fail "Legacy imports found in runtime code"
fi

echo "[guardrail] separation checks passed"

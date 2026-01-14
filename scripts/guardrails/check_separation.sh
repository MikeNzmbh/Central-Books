#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT_DIR"

TARGETS=(backend apps)
RG_EXCLUDES=(--glob '!legacy/**' --glob '!backend/reports/**')

fail() {
  echo "[guardrail] $1" >&2
  exit 1
}

if rg -n -i "django|allauth|manage\.py|SessionMiddleware|TemplateResponse|render_to_string" "${RG_EXCLUDES[@]}" "${TARGETS[@]}"; then
  fail "Django references found outside legacy/"
fi

if rg -n "legacy/" "${RG_EXCLUDES[@]}" "${TARGETS[@]}"; then
  fail "Legacy imports found in runtime code"
fi

echo "[guardrail] separation checks passed"

import json
from pathlib import Path

from django import template
from django.conf import settings

register = template.Library()


@register.filter
def get_item(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return None


_MANIFEST_CACHE = None
_MANIFEST_MTIME = None


def _get_manifest_path() -> Path:
    return (
        Path(settings.BASE_DIR)
        / "frontend"
        / "static"
        / "frontend"
        / ".vite"
        / "manifest.json"
    )


def _load_manifest() -> dict:
    global _MANIFEST_CACHE, _MANIFEST_MTIME

    manifest_path = _get_manifest_path()
    if not manifest_path.exists():
        return {}

    mtime = manifest_path.stat().st_mtime
    if _MANIFEST_CACHE is not None and _MANIFEST_MTIME == mtime:
        return _MANIFEST_CACHE

    with manifest_path.open("r", encoding="utf-8") as f:
        _MANIFEST_CACHE = json.load(f)
    _MANIFEST_MTIME = mtime
    return _MANIFEST_CACHE


def _find_entry(name: str, manifest: dict) -> tuple[str, dict] | tuple[None, None]:
    if not manifest:
        return None, None

    candidates = [
        name,
        f"{name}.tsx",
        f"{name}.ts",
        f"{name}.jsx",
        f"{name}.js",
    ]
    for key in candidates:
        entry = manifest.get(key)
        if entry:
            return key, entry
    return None, None


def _resolve_css_path(entry_key: str, manifest: dict, seen: set[str] | None = None) -> str:
    if not entry_key or not manifest:
        return ""
    if seen is None:
        seen = set()
    if entry_key in seen:
        return ""
    seen.add(entry_key)

    entry = manifest.get(entry_key)
    if not entry:
        return ""

    css_files = entry.get("css") or []
    if css_files:
        return css_files[0]

    for import_key in entry.get("imports") or []:
        css_path = _resolve_css_path(import_key, manifest, seen)
        if css_path:
            return css_path
    return ""


@register.simple_tag
def vite_asset(entry_name: str, kind: str = "js") -> str:
    manifest = _load_manifest()
    entry_key, entry = _find_entry(entry_name, manifest)
    if not entry:
        return ""

    if kind == "js":
        file_path = entry.get("file")
        if not file_path:
            return ""
        return f"frontend/{file_path.lstrip('/')}"

    if kind == "css":
        css_file = _resolve_css_path(entry_key, manifest)
        if not css_file:
            return ""
        return f"frontend/{css_file.lstrip('/')}"

    return ""

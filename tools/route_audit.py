"""CardDesk route audit utility.

Scans every template for literal url_for('endpoint') / url_for("endpoint") calls
and compares them to the Flask endpoints actually registered by app.py.

Run from the CardDesk project root:
    python tools/route_audit.py

Optional:
    python tools/route_audit.py --show-all
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Keep the audit from touching your real local/Render database while importing app.py.
os.environ.setdefault("CARDWATCH_DATA_DIR", str(PROJECT_ROOT / ".route_audit_data"))
os.environ.setdefault("CARDWATCH_DB_NAME", "route_audit.db")
os.environ.setdefault("CARDWATCH_SECRET_KEY", "route-audit-only")

URL_FOR_RE = re.compile(r"url_for\(\s*(['\"])(?P<endpoint>[^'\"]+)\1")


def collect_template_endpoints() -> dict[str, list[tuple[Path, int, str]]]:
    """Return endpoint -> [(file, line, source_line), ...]."""
    endpoints: dict[str, list[tuple[Path, int, str]]] = defaultdict(list)

    if not TEMPLATES_DIR.exists():
        raise FileNotFoundError(f"Templates folder not found: {TEMPLATES_DIR}")

    for template_path in sorted(TEMPLATES_DIR.rglob("*.html")):
        try:
            lines = template_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = template_path.read_text(errors="replace").splitlines()

        for line_no, line in enumerate(lines, start=1):
            for match in URL_FOR_RE.finditer(line):
                endpoint = match.group("endpoint")
                endpoints[endpoint].append((template_path, line_no, line.strip()))

    return endpoints


def load_registered_endpoints() -> set[str]:
    """Import app.py and return Flask's registered endpoint names."""
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from app import app  # type: ignore
    except Exception as exc:  # pragma: no cover - this is for dev troubleshooting
        print("\nERROR: Could not import app.py, so routes could not be audited.", file=sys.stderr)
        print(f"Reason: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        print("\nTry running this from the CardDesk project root with your venv active:", file=sys.stderr)
        print("    python tools/route_audit.py", file=sys.stderr)
        raise SystemExit(2)

    return set(app.view_functions.keys())


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit template url_for endpoints against registered Flask routes.")
    parser.add_argument("--show-all", action="store_true", help="Print all template endpoints and whether each exists.")
    args = parser.parse_args()

    template_endpoints = collect_template_endpoints()
    registered_endpoints = load_registered_endpoints()

    # Flask's built-in static endpoint is valid. Custom uploaded routes are checked normally.
    ignored = {"static"}
    missing = {
        endpoint: refs
        for endpoint, refs in template_endpoints.items()
        if endpoint not in registered_endpoints and endpoint not in ignored
    }

    if args.show_all:
        print("\nTemplate endpoints:")
        for endpoint in sorted(template_endpoints):
            status = "OK" if endpoint in registered_endpoints or endpoint in ignored else "MISSING"
            print(f"  {status:7} {endpoint}")

    print("\nCardDesk Route Audit")
    print("====================")
    print(f"Templates scanned: {len(list(TEMPLATES_DIR.rglob('*.html')))}")
    print(f"Template endpoints found: {len(template_endpoints)}")
    print(f"Registered Flask endpoints: {len(registered_endpoints)}")

    if not missing:
        print("\nPASS: No missing template routes found.")
        return 0

    print(f"\nFAIL: {len(missing)} missing endpoint(s) found:\n")
    for endpoint, refs in sorted(missing.items()):
        print(f"- {endpoint}")
        for path, line_no, source in refs[:8]:
            rel_path = path.relative_to(PROJECT_ROOT)
            print(f"    {rel_path}:{line_no}  {source}")
        if len(refs) > 8:
            print(f"    ...and {len(refs) - 8} more reference(s)")
        print()

    print("Fix: add/register the missing route function, or update the template endpoint name.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

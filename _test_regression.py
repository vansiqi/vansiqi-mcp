"""Full regression test — run after every bugfix (and before every push).

Covers the current architecture: server.py + adapters/kyb_db.py +
normalizers.py over data/kyb.db (single authoritative snapshot).

Usage: py _test_regression.py   (exit 0 = all green)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent

errors: list[str] = []

def check(name: str, cond: bool, detail: str = "") -> None:
    status = "✅" if cond else "❌"
    print(f"  {status} {name}" + (f" ({detail})" if detail else ""))
    if not cond:
        errors.append(f"{name} {detail}")

# ── 1. Syntax check all project .py files ────────────────────────
print("=== 1. Syntax Check ===")
import ast
for f in sorted(ROOT.rglob("*.py")):
    if "__pycache__" in f.parts:
        continue
    try:
        ast.parse(f.read_text(encoding="utf-8"))
        print(f"  ✅ {f.relative_to(ROOT)}")
    except SyntaxError as e:
        print(f"  ❌ {f.relative_to(ROOT)}: {e}")
        errors.append(f"syntax: {f}")

# ── 2. Import all runtime modules ────────────────────────────────
print("\n=== 2. Import Check ===")
try:
    import server  # noqa: F401
    print("  ✅ server.py (FastMCP loaded)")
except Exception as e:
    print(f"  ❌ server.py: {e}")
    errors.append(f"import server: {e}")
try:
    from adapters import GEO_MAP, KybDBAdapter, normalize_number  # noqa: F401
    print("  ✅ adapters.kyb_db (single data layer)")
except Exception as e:
    print(f"  ❌ adapters.kyb_db: {e}")
    errors.append(f"import adapters: {e}")

# ── 3. Data layer contract ───────────────────────────────────────
print("\n=== 3. Data Layer Contract ===")
from server import query_registration, list_supported_countries

ls = list_supported_countries()
codes = [c["code"] for c in ls["countries"]]
check("list_supported_countries == SG/AU/US-FL/UK", codes == ["SG", "AU", "US-FL", "UK"], str(codes))
check("no auth required anywhere", all(not c["auth_required"] for c in ls["countries"]))
check("data_cutoff advertised", all(c.get("data_cutoff") for c in ls["countries"]))

samples = [
    ("US-FL", "l16000216990", "FLIP THAT REO LLC"),  # lowercase input
    ("AU", "004 028 077", "BHP GROUP LIMITED"),       # spaced input
    ("UK", "08209948", "! LTD"),
    ("SG", "199202468E", "ACCESS BPO PTE. LTD."),
]
for country, num, expect in samples:
    r = query_registration(country, num, query_type="number")
    ok = r.get("found") and r["result"]["entity_name"].upper() == expect.upper()
    check(f"number lookup {country} {num!r}", bool(ok))

r = query_registration("US-FL", "L16000216990", query_type="number")["result"]
for field in ("country", "registration_number", "entity_name", "entity_type", "status",
              "filing_date", "principal_address", "data_source", "last_verified",
              "source_url", "raw"):
    check(f"schema has {field}", field in r)
check("last_verified is snapshot date", r.get("last_verified") in ("2026-10-22", "2026-10-23"),
      str(r.get("last_verified")))
check("source_url is official link", "sunbiz.org" in (r.get("source_url") or ""))
check("FL status I -> Inactive", r.get("status") == "Inactive", str(r.get("status")))
check("FL type FLAL -> LLC", r.get("entity_type") == "LLC", str(r.get("entity_type")))

# ── 4. Name search (FTS5) ────────────────────────────────────────
print("\n=== 4. Name Search ===")
r = query_registration("AU", "BHP", query_type="name", limit=5)
check("AU name search finds BHP GROUP LIMITED",
      r.get("found") and any(x["entity_name"] == "BHP GROUP LIMITED" for x in r["results"]))
r = query_registration("UK", "British Airways", query_type="name", limit=5)
check("UK name search works", r.get("found"))

# ── 5. Boundaries ────────────────────────────────────────────────
print("\n=== 5. Boundaries ===")
check("empty query errors", "error" in query_registration("US-FL", "", query_type="number"))
check("unknown country errors", "error" in query_registration("XX", "test"))
r = query_registration("US-FL", "!!!###", query_type="name")
check("dirty chars safe", isinstance(r, dict) and r.get("found") in (True, False))
check("missing number -> found False",
      query_registration("US-FL", "L99999999999", query_type="number").get("found") is False)

# ── 6. Render pipeline parity (satellite pages same source) ─────
print("\n=== 6. Satellite Page Reconciliation (spot) ===")
dist = ROOT / "render" / "dist" / "company"
CODE_MAP = {"gb": "UK", "sg": "SG", "au": "AU", "us-fl": "US-FL"}
spot = {
    "gb": "08209948", "sg": "199202468e", "au": "004028077", "us-fl": "l16000216990",
}
if dist.is_dir():
    for jur_dir, num in spot.items():
        f = dist / jur_dir / f"{num}.html"
        if not f.is_file():
            check(f"dist page {jur_dir}/{num}", False, "missing dist page (run build_dist.py)")
            continue
        r = query_registration(CODE_MAP[jur_dir], num, query_type="number")
        check(f"dist page {jur_dir}/{num} -> MCP found", r.get("found") is True)
else:
    print("  ⚠️ render/dist not built — skip reconciliation spot checks")

# ── Verdict ──────────────────────────────────────────────────────
print("\n" + "=" * 50)
if errors:
    print(f"REGRESSION FAIL ({len(errors)}):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("REGRESSION OK — all checks passed")

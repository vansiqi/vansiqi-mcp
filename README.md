# vansiqi-mcp

> Global business registration verification for AI agents — unified MCP server built on official government open data.

## What this is

A single MCP tool that lets any AI agent query business registry records across **multiple jurisdictions** through a **unified interface**. All queries run on a **local snapshot of official bulk records** (`kyb.db`, 24.6M rows) — the exact same dataset that powers [vansiqi.com](https://vansiqi.com). No third-party aggregator, no API keys, no upstream network calls at query time.

Built with a **GEO adapter architecture**: each jurisdiction maps to one row-source in the local database, normalized into one consistent output schema. Adding a new country is one new ingestion pipeline, no changes to query code.

## Supported jurisdictions

| Code | Jurisdiction | Source (snapshot) | Records | Auth |
|------|-------------|-------------------|---------|------|
| `SG` | Singapore | ACRA via data.gov.sg | 1,938,342 | None |
| `AU` | Australia | ASIC via data.gov.au | 4,018,252 | None |
| `US-FL` | USA (Florida) | Sunbiz SFTP | 12,987,600 | None |
| `UK` | United Kingdom | Companies House bulk | 5,704,711 | None |

Total coverage: **24,648,905 entities** (snapshot as of 2026-10-23).

> **Snapshot semantics**: data reflects the official bulk records as of the
> ingestion date. Every result carries `last_verified` (record snapshot date)
> and `source_url` (official register link) — verify time-critical decisions
> against the official register. Snapshot refreshes are driven by the update
> pipeline; new registry values outside the normalization dictionaries fall
> through with their raw codes preserved.

## Installation

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

## Usage

### In Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "vansiqi-mcp": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

> **Note**: `kyb.db` must be present at `data/kyb.db` relative to `server.py`.
> No API keys or environment variables are required.

### In any MCP client (stdio)

```bash
python server.py
```

### SSE mode (remote deployment)

```bash
python server.py --transport sse --host 0.0.0.0 --port 8000
```

## Tools

### `query_registration`

Query a business entity record from an official government register.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `country` | string | Jurisdiction code: `SG`, `AU`, `US-FL`, `UK` |
| `query` | string | Company name OR registration number |
| `query_type` | string | `name` (fuzzy search) or `number` (exact lookup). Default: `name` |
| `limit` | int | Max results for name search. Default 20, max 100 |

**Example agent prompts:**

- "Is Tesla registered in the UK?"
- "查一下 Singapore Airlines 在新加坡的注册状态"
- "Get the registered agent for Apple Inc in Florida"

**Unified response schema:**

```json
{
  "found": true,
  "country": "SG",
  "query": "Singapore Airlines",
  "count": 3,
  "results": [
    {
      "country": "SG",
      "region": null,
      "registration_number": "01234567X",
      "entity_name": "SINGAPORE AIRLINES LIMITED",
      "entity_type": "Corporation",
      "status": "Active",
      "filing_date": "1972-10-28",
      "dissolution_date": null,
      "registered_agent": null,
      "principal_address": "1 Scotts Road, Singapore 228208",
      "industry_code": "51101",
      "industry_description": "PASSENGER AIR TRANSPORT NSC",
      "officers_count": null,
      "data_source": "SG ACRA (via data.gov.sg bulk snapshot)",
      "last_verified": "2026-10-23",
      "source_url": "https://www.bizfile.gov.sg/ (UEN 01234567X)",
      "raw": { /* original fields from the source */ }
    }
  ]
}
```

Status enum: `Active`, `Inactive`, `Dissolved`, `Merged`, `Liquidation`, `Unknown`.
Registry values outside the normalization dictionaries preserve their raw codes
in the `raw` field (gettext-style fallback, never silently dropped).

### `list_supported_countries`

Returns all queryable jurisdictions with data-source info, exact record counts, and the snapshot cutoff date. Call this first if unsure which `country` code to use.

## Architecture

```
server.py              ← FastMCP app, exposes 2 tools
normalizers.py         ← Unified schema + cross-GEO status/type mapping
adapters/
  kyb_db.py           ← Single data layer: read-only SQLite over kyb.db
dictionaries/
  {gb,sg,au,us_fl}.yml ← Official enum dictionaries (full DISTINCT coverage)
data/
  kyb.db              ← 24,648,905 rows, 4 jurisdictions (snapshot)
```

One adapter class (`KybDBAdapter`) serves all four jurisdictions: exact
registration-number lookup via the UNIQUE index (~1 ms) and full-text name
search via FTS5 with bm25 ranking (~100 ms).

```python
search_by_name(name: str, limit: int) -> list[dict]
get_by_number(number: str) -> dict | None
```

Raw source rows flow through `normalizers.build_unified_record()` which translates country-specific fields into the unified schema before returning to the agent, with per-GEO normalization dictionaries (`dictionaries/*.yml`) mapping every official status/type enum to its normalized value.

## Why this exists

Most agent projects need some form of KYB (Know Your Business) verification — confirming a counterparty exists, is active, and hasn't been dissolved. The data is public in every jurisdiction, but each country exposes it differently (API vs CSV vs SFTP, different field names, different status vocabularies).

This server does the tedious work once, so agent developers can call one tool instead of integrating with N government APIs.

## License

MIT

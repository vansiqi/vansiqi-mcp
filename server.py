"""
kyb-mcp-server — Global Business Registration Verification MCP Server

面向 AI agent 的 KYB 企业注册数据查询插件。
统一接口，多 GEO 适配器，零成本开放数据源。

Usage:
    python server.py                # 以 stdio 模式运行（MCP 客户端自动启动）
    python server.py --transport sse # 以 SSE 模式运行（远程部署）
"""

from __future__ import annotations

import argparse
from typing import Any

from fastmcp import FastMCP

from adapters.kyb_db import GEO_MAP, KybDBAdapter, normalize_number

# ── 初始化 MCP server ─────────────────────────────────────────
mcp = FastMCP(
    name="vansiqi-mcp",
    instructions=(
        "Global business registration verification for AI agents. "
        "Query official government registers across 4 jurisdictions "
        "(Singapore, Australia, US-Florida, United Kingdom — 24.6M records) "
        "for company status, filing dates, registered agents, and addresses. "
        "All data is a local snapshot of official bulk records (same source "
        "dataset that powers vansiqi.com); every result carries the official "
        "source URL for verification. Always cite source_url when reporting a "
        "company's status."
    ),
    version="0.2.0",
)

# ── 适配器注册表（country → adapter 实例） ─────────────────────
_adapters: dict[str, Any] = {}


# ── 单一数据源：所有 GEO 元信息（list_supported_countries 和 _SUPPORTED_COUNTRIES 都从这里生成） ──
# records 为 kyb.db 权威定数（2026-10-23 入库终审，行级精确）；
# 四国共用本地快照 kyb.db，与 vansiqi.com 卫星页同源同数。
_GEO_REGISTRY: list[dict[str, Any]] = [
    {
        "code": "SG",
        "name": "Singapore",
        "source": "ACRA (via data.gov.sg bulk snapshot)",
        "records": "1,938,342",
        "data_cutoff": "2026-10-23",
        "auth_required": False,
        "available": True,
    },
    {
        "code": "AU",
        "name": "Australia",
        "source": "ASIC (via data.gov.au bulk snapshot)",
        "records": "4,018,252",
        "data_cutoff": "2026-10-23",
        "auth_required": False,
        "available": True,
    },
    {
        "code": "US-FL",
        "name": "United States (Florida)",
        "source": "Florida Division of Corporations (Sunbiz SFTP snapshot)",
        "records": "12,987,600",
        "data_cutoff": "2026-10-23",
        "auth_required": False,
        "available": True,
    },
    {
        "code": "UK",
        "name": "United Kingdom",
        "source": "Companies House bulk snapshot",
        "records": "5,704,711",
        "data_cutoff": "2026-10-23",
        "auth_required": False,
        "available": True,
    },
]

# _SUPPORTED_COUNTRIES 只取 available=True 的 code
_SUPPORTED_COUNTRIES = [g["code"] for g in _GEO_REGISTRY if g["available"]]


# ── Tool 2: list_supported_countries ──────────────────────────
@mcp.tool()
def list_supported_countries() -> dict[str, Any]:
    """Return all jurisdictions this server can query, with data source info.

    Call this first if you are unsure which country code to use, or to confirm
    data freshness and coverage before running a query.

    Returns:
        dict with:
          - countries: list of GEO entries. Each has code, name, source, records
            (exact row count), data_cutoff (snapshot date of the local dataset),
            auth_required (bool), available (bool).
          - usage_hint: how to use this data.
    """
    return {
        "countries": [
            {
                "code": g["code"],
                "name": g["name"],
                "source": g["source"],
                "records": g["records"],
                "data_cutoff": g["data_cutoff"],
                "auth_required": g["auth_required"],
            }
            for g in _GEO_REGISTRY if g["available"]
        ],
        "usage_hint": (
            "Use the 'code' field as the country parameter in query_registration. "
            "All four jurisdictions run on a local snapshot of official bulk "
            "records — no API keys needed. Data is as of data_cutoff; verify "
            "critical decisions against the official register via each result's "
            "source_url."
        ),
    }


def _init_adapter(country: str) -> KybDBAdapter:
    """按需初始化 adapter（本地 SQLite 只读连接，线程内复用）。"""
    if country not in GEO_MAP:
        raise ValueError(
            f"Unsupported country: {country}. "
            f"Supported: {', '.join(_SUPPORTED_COUNTRIES)}"
        )
    if country not in _adapters:
        _adapters[country] = KybDBAdapter(country)
    return _adapters[country]


# ── Tool 1: query_registration（统一入口） ────────────────────
@mcp.tool()
def query_registration(
    country: str,
    query: str,
    query_type: str = "name",
    limit: int = 20,
) -> dict[str, Any]:
    """Query a business entity registration record from an official government register.

    Use this tool to verify whether a company is legally registered, check its
    current status, filing date, registered agent, and principal address.
    Data is a local snapshot of official bulk records (no third-party aggregator);
    each result includes source_url so you can verify against the official register.

    Args:
        country: Jurisdiction code. One of "SG" (Singapore), "AU" (Australia),
            "US-FL" (USA Florida), "UK" (United Kingdom).
        query: The company name OR registration number (UEN for SG, ACN for AU,
            DocNumber for US-FL, company_number for UK). Registration numbers
            are normalized automatically (spaces/dashes/case are ignored).
        query_type: How to interpret `query`. "name" (default) does full-text
            search across the register snapshot; "number" does exact lookup by
            registration ID.
        limit: Maximum results when query_type is "name". Default 20, max 100.

    Returns:
        A unified JSON object (or list of objects) with these fields:
        - country, region, registration_number, entity_name
        - entity_type (normalized enum: Corporation, LLC, LP, LLP, Partnership,
          Sole Proprietorship, Foreign Entity, Other)
        - status (normalized enum: Active, Inactive, Dissolved, Merged,
          Liquidation, Unknown)
        - filing_date, dissolution_date, registered_agent, principal_address
        - industry_code, industry_description, officers_count (varies by GEO)
        - data_source (exact government source), last_verified (snapshot date
          of this record)
        - source_url (official register page to verify this record)
        - raw (original fields from the source, for advanced use)

    When to call:
        - Verify a counterparty's legal existence before signing a contract
        - Check if a supplier is currently in Good Standing
        - Find the registered agent or official address for service of process
        - Cross-reference a company registration number against official records

    Do NOT call when:
        - You need identity verification of a natural person (use IDV tools instead)
        - You need sanctions screening (use OpenSanctions MCP instead)
        - You need real-time UBO/beneficial ownership tracing
        - You need same-day real-time status (snapshot data — use source_url
          to confirm on the official register for time-critical decisions)
    """
    country = country.strip().upper()
    query = query.strip()
    query_type = query_type.strip().lower()

    if country not in _SUPPORTED_COUNTRIES:
        return {
            "error": f"Unsupported country '{country}'",
            "supported_countries": _SUPPORTED_COUNTRIES,
        }

    if not query:
        return {"error": "query is required"}

    adapter = _init_adapter(country)

    if query_type == "number":
        result = adapter.get_by_number(normalize_number(query))
        if result is None:
            return {"found": False, "country": country, "query": query}
        return {"found": True, "country": country, "query": query, "result": result}

    # default: search by name
    limit = max(1, min(int(limit), 100))
    results = adapter.search_by_name(query, limit=limit)
    return {
        "found": len(results) > 0,
        "country": country,
        "query": query,
        "count": len(results),
        "results": results,
    }


# ── 入口 ──────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="vansiqi-mcp MCP server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "stdio":
        # 默认 stdio：MCP 客户端（Claude Desktop / Trae / Cline）自动 spawn 这个进程
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()

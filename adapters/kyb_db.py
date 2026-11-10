"""
adapters/kyb_db.py — 唯一数据层：本地权威库 kyb.db（24,648,905 行四国登记快照）

架构原则（对应项目硬约束）：
- 所有官方数据源本地留存完整副本，不直接依赖上游接口提供查询服务
- MCP 与卫星页（vansiqi.com）同源同数：同一份 kyb.db
- 只读连接（mode=ro），绝不写库

性能：
- get_by_number 走 UNIQUE(jurisdiction, company_number) 自动索引，~1ms
- search_by_name 走 FTS5（external content，columnsize=0）+ bm25 rank，~100ms
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from normalizers import build_unified_record

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "kyb.db"

# ── GEO 注册表（code → 库 jurisdiction 与输出元信息）────────────────
# country/region 输出值与旧 adapter 保持一致，对 MCP 客户端向后兼容。
GEO_MAP: dict[str, dict[str, Any]] = {
    "SG": {
        "jurisdiction": "sg",
        "country": "SG",
        "region": None,
        "data_source": "SG ACRA (via data.gov.sg bulk snapshot)",
    },
    "AU": {
        "jurisdiction": "au",
        "country": "AU",
        "region": None,
        "data_source": "AU ASIC (via data.gov.au bulk snapshot)",
    },
    "US-FL": {
        "jurisdiction": "us_fl",
        "country": "US",
        "region": "FL",
        "data_source": "US Florida Sunbiz SFTP snapshot",
    },
    "UK": {
        "jurisdiction": "gb",
        "country": "UK",
        "region": None,
        "data_source": "UK Companies House bulk snapshot",
    },
}

# ── 状态映射（raw 精确值 → 统一枚举）────────────────────────────────
# 枚举全集来自 dictionaries/*.yml（kyb.db 全量 SELECT DISTINCT 2026-10-26 对账）。
# 原则：枚举只有六值，程序中/风险态一律归 Inactive 或 Liquidation（保守方向，
# 防止把"有风险信号"的公司误报为 Active/Good Standing）；语义细节看 raw.status。

_STATUS_MAP: dict[str, dict[str, str]] = {
    "us_fl": {
        "A": "Active",
        "I": "Inactive",
    },
    "au": {
        "REGD": "Active",       # Registered
        "DRGD": "Dissolved",    # Deregistered
        "SOFF": "Inactive",     # Strike-off action in progress
        "EXAD": "Inactive",     # Under external administration / controller appointed
        "NOAC": "Inactive",     # Not active
        "DISS": "Dissolved",    # Dissolved by special act of parliament
    },
    "gb": {
        "Active": "Active",
        # 保守：除名程序中不作为 Good Standing 输出
        "Active - Proposal to Strike off": "Inactive",
        "Liquidation": "Liquidation",
        "In Administration": "Liquidation",
        "In Administration/Administrative Receiver": "Liquidation",
        "In Administration/Receiver Manager": "Liquidation",
        "ADMINISTRATION ORDER": "Liquidation",
        "ADMINISTRATIVE RECEIVER": "Liquidation",
        "RECEIVERSHIP": "Liquidation",
        "RECEIVER MANAGER / ADMINISTRATIVE RECEIVER": "Liquidation",
        "Live but Receiver Manager on at least one charge": "Inactive",
        "Voluntary Arrangement": "Inactive",
        "VOLUNTARY ARRANGEMENT / RECEIVER MANAGER": "Inactive",
        "VOLUNTARY ARRANGEMENT / ADMINISTRATIVE RECEIVER": "Inactive",
    },
    "sg": {
        "Live Company": "Active",
        "Live": "Active",
        "Live (Receiver or Receiver and Manager appointed)": "Inactive",
        "Suspended": "Inactive",
        "To Be Ceased": "Inactive",
        "Cancellation In Progress": "Inactive",
        "Gazetted To Be Struck Off": "Inactive",
        "Struck Off": "Dissolved",
        "Struck Off (Early Dissolution)": "Dissolved",
        "Struck Off (Early Dissolution - simplified winding up)": "Dissolved",
        "Terminated": "Dissolved",
        "Cancelled": "Dissolved",
        "Cancelled (Non-Renewal)": "Dissolved",
        "Ceased Registration": "Dissolved",
        "Ceased Registration (Transferred to Singapore)": "Dissolved",
        "Dissolved": "Dissolved",
        "Dissolved - Members Voluntary Winding Up": "Dissolved",
        "Dissolved - Compulsory Winding Up (Insolvency)": "Dissolved",
        "Dissolved - Creditors Voluntary Winding Up": "Dissolved",
        "Dissolved - Compulsory Winding Up": "Dissolved",
        "Dissolved - Partner Voluntary Winding Up": "Dissolved",
        "Dissolved - Simplified Winding Up": "Dissolved",
        "Dissolved - Pursuant to Section 212(1)(D) Of The Companies Act": "Dissolved",
        "Converted To LLP": "Dissolved",
        "Registration expired and has not been renewed": "Dissolved",
        "Removed (Applied To Be Revoked)": "Dissolved",
        "Removed (Dissolved)": "Dissolved",
        "Revoked (Failed To Transfer Registration)": "Dissolved",
        "Amalgamated": "Merged",
        "In Liquidation": "Liquidation",
        "In Liquidation - Compulsory Winding Up (Insolvency)": "Liquidation",
        "In Liquidation - Members voluntary winding up": "Liquidation",
        "In Liquidation - Creditors voluntary winding up": "Liquidation",
        "In Liquidation - Compulsory Winding Up": "Liquidation",
        "In Liquidation - Simplified Winding Up": "Liquidation",
        "In Liquidation - Partners voluntary winding up": "Liquidation",
        "Under Judicial Management": "Liquidation",
    },
}

# ── 实体类型映射（raw 精确值 → 统一枚举）────────────────────────────

_TYPE_MAP: dict[str, dict[str, str]] = {
    "us_fl": {
        "FLAL": "LLC",
        "FORL": "LLC",
        "DOMP": "Corporation",
        "FORP": "Corporation",
        "DOMNP": "Corporation",
        "FORNP": "Corporation",
        "DOMLP": "LP",
        "FORLP": "LP",
        "NPREG": "Other",
        "TRUST": "Other",
        "AGENT": "Other",
        "COOP": "Other",
    },
    "au": {
        "APTY": "Corporation",
        "APUB": "Corporation",
        "FNOS": "Foreign Entity",
        "RACN": "Other",
        "CCIV": "Other",
    },
    "gb": {
        "Private Limited Company": "Corporation",
        "PRI/LTD BY GUAR/NSC (Private, limited by guarantee, no share capital)": "Corporation",
        "PRI/LBG/NSC (Private, Limited by guarantee, no share capital, use of 'Limited' exemption)": "Corporation",
        "PRIV LTD SECT. 30 (Private limited company, section 30 of the Companies Act)": "Corporation",
        "Public Limited Company": "Corporation",
        "Old Public Company": "Corporation",
        "Community Interest Company": "Corporation",
        "Royal Charter Company": "Corporation",
        "Limited Liability Partnership": "LLP",
        "Limited Partnership": "LP",
        "Overseas Entity": "Foreign Entity",
        "Scottish Partnership": "Partnership",
        "Charitable Incorporated Organisation": "Other",
        "Scottish Charitable Incorporated Organisation": "Other",
        "Registered Society": "Other",
        "Industrial and Provident Society": "Other",
        "Private Unlimited Company": "Other",
        "Private Unlimited": "Other",
        "Investment Company with Variable Capital": "Other",
        "Investment Company with Variable Capital(Umbrella)": "Other",
        "Investment Company with Variable Capital (Securities)": "Other",
        "United Kingdom Economic Interest Grouping": "Other",
        "United Kingdom Societas": "Other",
        "Protected Cell Company": "Other",
        "Further Education and Sixth Form College Corps": "Other",
        "Converted/Closed": "Other",
        "Other company type": "Other",
        "Other Company Type": "Other",
    },
    "sg": {
        "Local Company": "Corporation",
        "Sole Proprietorship/ Partnership": "Partnership",
        "Limited Liability Partnership": "LLP",
        "Limited Partnership": "LP",
        "Foreign Company Branch": "Foreign Entity",
    },
}


def normalize_number(raw_number: str) -> str:
    """注册号归一化：去空格/连字符/点 + 大写。

    兼容人类书写习惯（"004 028 077" → "004028077"），
    库内注册号均已规范化（入库时 trim/大写）。
    """
    return re.sub(r"[\s.\-]+", "", raw_number).upper()


def _fts_expression(query: str) -> str | None:
    """把用户输入转成安全的 FTS5 MATCH 表达式（词前缀 AND）。

    FTS 语法字符（引号/括号/运算符）一律丢弃，防注入与语法错误。
    返回 None 表示无有效词。
    """
    words = re.findall(r"[A-Za-z0-9]+", query)
    if not words:
        return None
    return " AND ".join(w + "*" for w in words)


class KybDBAdapter:
    """单国查询适配器：读 kyb.db，输出统一 schema（复用 normalizers）。"""

    def __init__(self, code: str) -> None:
        geo = GEO_MAP[code]
        self.code = code
        self.country = geo["country"]
        self.region = geo["region"]
        self.jurisdiction = geo["jurisdiction"]
        self.data_source = geo["data_source"]
        self._local = threading.local()

    # ── 连接管理（每线程一条只读连接）────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(f"file:{_DB_PATH.as_posix()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    # ── 按注册号精确查询 ─────────────────────────────────────────
    def get_by_number(self, number: str) -> dict[str, Any] | None:
        row = self._conn().execute(
            "SELECT * FROM company WHERE jurisdiction=? AND company_number=?",
            (self.jurisdiction, normalize_number(number)),
        ).fetchone()
        return self._normalize(row) if row else None

    # ── 按名字搜索（FTS5 + bm25 rank）────────────────────────────
    def search_by_name(self, name: str, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        expr = _fts_expression(name)
        if expr is None:
            return []
        rows = self._conn().execute(
            "SELECT c.* FROM company_fts f "
            "JOIN company c ON c.rowid = f.rowid "
            "WHERE company_fts MATCH ? AND c.jurisdiction = ? "
            "ORDER BY rank LIMIT ?",
            (expr, self.jurisdiction, limit),
        ).fetchall()
        # FTS 前缀匹配对极短/停用词可能过宽，兜底一次子串语义不强求
        return [self._normalize(r) for r in rows]

    # ── kyb.db 行 → 统一 schema ─────────────────────────────────
    def _normalize(self, row: sqlite3.Row) -> dict[str, Any]:
        raw = json.loads(row["raw"]) if row["raw"] else {}

        record = build_unified_record(
            country=self.country,
            region=self.region,
            registration_number=row["company_number"],
            entity_name=row["name"],
            raw_status=row["status_raw"],
            raw_entity_type=row["entity_type_raw"] or None,
            filing_date=row["filing_date"] or None,
            dissolution_date=row["dissolution_date"] or None,
            registered_agent=row["agent"] or None,
            address_parts={"principal_address": row["address"]} if row["address"] else {},
            industry_code=row["industry_raw"] or None,
            industry_description=self._industry_description(raw),
            officers_count=self._officers_count(raw),
            data_source=self.data_source,
            last_verified=row["retrieved_at"] or "",
            raw=raw,
        )
        # 统一枚举优先走本 GEO 的精确映射（覆盖 100% 官方枚举），
        # 字典外新值落到 normalizers 的通用别名兜底，最终兜底 Unknown/Other。
        status_map = _STATUS_MAP.get(self.jurisdiction, {})
        if row["status_raw"] in status_map:
            record["status"] = status_map[row["status_raw"]]
        type_map = _TYPE_MAP.get(self.jurisdiction, {})
        if (row["entity_type_raw"] or None) in type_map:
            record["entity_type"] = type_map[row["entity_type_raw"]]
        # 官方核对链接：KYB 项目铁律，每条记录必附
        record["source_url"] = row["source_url"] or None
        return record

    # ── 从 raw JSON 提取补充字段（按国各自的真实字段）────────────
    @staticmethod
    def _industry_description(raw: dict[str, Any]) -> str | None:
        # SG: SSIC 描述；GB: SIC text；AU: Class/Sub Class 已在 industry_code；FL: 无行业字段
        v = raw.get("primary_ssic_description")
        if v and str(v).strip().lower() not in ("na", ""):
            return str(v)
        sic = raw.get("SICCode.SicText_1")
        if sic and str(sic).strip().lower() not in ("none available", ""):
            return str(sic)
        return None

    @staticmethod
    def _officers_count(raw: dict[str, Any]) -> int | None:
        v = raw.get("no_of_officers")
        if v in (None, "", "na"):
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

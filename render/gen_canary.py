# -*- coding: utf-8 -*-
"""
金丝雀批量生成器（gen_canary.py）
- 选样：审批定稿标准（在营/GB 排休眠/名字 8-60 且两词以上/无脏字符/登记满 3 年）
  + 快照种子确定性抽样（同库同种子结果恒定，可复现）
- 产量：每国 500 页 → wave1=前 50/国（200 页首批），wave2=其余 450/国（1800 页）
- 产物：
    render/canary/{jur}/{num}.html   （仅 wave1 首批）
    render/canary/wave1-list.csv / wave2-list.csv  （选样名单，供抽查与复现）
    render/canary/sitemap-wave1.xml / sitemap-wave2.xml
- 复用 gen_pages.py 的 build()（模板唯一事实源），PREVIEW 翻转为生产路由
"""
from __future__ import annotations

import csv
import hashlib
import bisect
import io
import os
import sqlite3
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pages as G  # noqa: E402  (build/esc/tr/VERIFY/LICENSE 等)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canary")
DB = r"d:\S.Q\kyb-mcp-server\data\kyb.db"
SEED = "kyb-canary-1"
PER_JUR_TOTAL = 500   # 每国总量
PER_JUR_WAVE1 = 50    # 首批（试探）
CUTOFF = (date.today() - timedelta(days=365 * 3)).isoformat()  # 登记满 3 年
JUNK = ('*', '<', '>', '"', '\\')
LIVE = {"gb": "Active", "sg": "Live Company", "au": "REGD", "us_fl": "A"}
JUR_DIR = {"us_fl": "us-fl"}  # 目录名（url 用 -，键用 _）

# 各国注册处显示名 / 登记动词 / 编号标签
META = {
    "gb":    dict(reg="Companies House", reg_zh="英国公司登记处", verb="incorporated at Companies House on",
                  verb_zh="在英国公司登记处注册", label="company number", label_zh="公司编号",
                  site="https://find-and-update.company-information.service.gov.uk/company/"),
    "sg":    dict(reg="ACRA", reg_zh="新加坡会计与企业管制局", verb="registered with ACRA on",
                  verb_zh="在 ACRA 登记", label="UEN", label_zh="UEN 统一识别码",
                  site="https://www.bizfile.gov.sg/"),
    "au":    dict(reg="ASIC", reg_zh="澳大利亚证券与投资委员会", verb="registered with ASIC since",
                  verb_zh="起在 ASIC 登记", label="ACN", label_zh="ACN 编号",
                  site="https://abr.business.gov.au/"),
    "us_fl": dict(reg="Sunbiz", reg_zh="佛罗里达州务司", verb="filed with the Florida Division of Corporations on",
                  verb_zh="在佛罗里达州务司登记", label="document number", label_zh="文件号",
                  site="https://search.sunbiz.org/"),
}
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]


def w(s):
    print(s, flush=True)


def an(word):
    return "an" if word[:1].upper() in "AEIOU" else "a"


def fmt_date(iso, zh=False):
    """ISO → '13 August 1885' / '1885 年 8 月 13 日'；空/坏值如实 unknown。"""
    if not iso or len(iso) != 10 or iso[4] != "-" or iso[7] != "-":
        return "unknown" if not zh else "未知"
    y, m, d = iso[:4], int(iso[5:7]), int(iso[8:10])
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return "unknown" if not zh else "未知"
    return f"{d} {MONTHS_EN[m - 1]} {y}" if not zh else f"{y} 年 {m} 月 {d} 日"


def gb_titlecase(addr):
    """GB 地址源为全大写，按 Companies House 官网惯例转 Title Case。
    含数字的 token（邮编 HG1 1ND、门牌 9）原样保留。"""
    out = []
    for tok in addr.split(" "):
        if not tok:
            out.append(tok)
        elif any(c.isdigit() for c in tok):
            out.append(tok)                     # 邮编/门牌号不动
        elif tok.isupper() and len(tok) > 1:
            out.append(tok.capitalize())
        else:
            out.append(tok)
    return " ".join(out)


def sg_address(addr):
    """SG 源 'block, street, level, unit, building, postal' → ACRA 官网惯例：
    '8 BURN ROAD, #16-16, TRIVEX, SINGAPORE 369977'。段数不符则原样返回。"""
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) != 6:
        return addr
    block, street, level, unit, building, postal = parts
    if not block or not street:
        return addr
    s = f"{block} {street}"
    if level and unit:
        s += f", #{level}-{unit}"
    if building:
        s += f", {building}"
    s += f", SINGAPORE {postal}"
    return s


def fl_agent(agent):
    """FL 源 'THOUBBORON          GARY          S'（姓在前）→ Sunbiz 官网格式
    'THOUBBORON, GARY S'。已含逗号或单词则原样；大小写不改（转录）。"""
    a = " ".join(agent.split())
    if not a or "," in a or " " not in a:
        return a
    first, rest = a.split(" ", 1)
    return f"{first}, {rest}"


def b(txt, raw):
    return f"<b>{txt}</b><span class='raw'>[{raw}]</span>"


def verify_url(jur, num, site):
    return site + num if jur == "gb" else site


def build_page(jur, num, name, st_raw, ty_raw, ind, fd, addr, agent, retrieved):
    m = META[jur]
    st = G.tr(jur, "status", st_raw)
    ty = G.tr(jur, "entity_type", ty_raw)
    d_en, d_zh = fmt_date(fd), fmt_date(fd, zh=True)
    v_en, v_zh = G.VERIFY[jur]
    vurl = verify_url(jur, num, m["site"])
    dirjur = JUR_DIR.get(jur, jur)
    lab = m["label"]

    # acn 行
    acn_en = (f"United Kingdom · Company number <code>{G.esc(num)}</code>" if jur == "gb" else
              f"Singapore · UEN <code>{G.esc(num)}</code>" if jur == "sg" else
              f"Australia · ACN <code>{G.esc(num)}</code>" if jur == "au" else
              f"Florida, USA · Document number <code>{G.esc(num)}</code>")
    acn_zh = (f"英国 · 公司编号 <code>{G.esc(num)}</code>" if jur == "gb" else
              f"新加坡 · UEN 统一识别码 <code>{G.esc(num)}</code>" if jur == "sg" else
              f"澳大利亚 · ACN 编号 <code>{G.esc(num)}</code>" if jur == "au" else
              f"美国佛罗里达州 · 文件号 <code>{G.esc(num)}</code>")

    # 答案框
    nm, numx = G.esc(name), G.esc(num)
    sten, stzh = G.esc(st["en"]), G.esc(st["zh"])
    if jur == "au":
        a_en = (f"{nm} (ACN {numx}) is {an(ty['en'])} <b>{G.esc(ty['en'])}</b> "
                f"registered with ASIC since <b>{d_en}</b>. As of the {retrieved} snapshot "
                f"the register shows its status as <b>{sten}</b> [{G.esc(st_raw)}].")
        a_zh = (f"{nm}（ACN {numx}）是一家<b>{G.esc(ty['zh'])}</b>，自 <b>{d_zh}</b>{m['verb_zh']}。"
                f"截至 {retrieved} 快照，登记状态为<b>「{stzh}」</b>（官方原词 {G.esc(st_raw)}）。")
    else:
        a_en = (f"{nm} ({lab} {numx}) is {an(ty['en'])} <b>{G.esc(ty['en'])}</b> "
                f"{m['verb']} <b>{d_en}</b>. As of the {retrieved} snapshot "
                f"the register shows its status as <b>{sten}</b> [{G.esc(st_raw)}].")
        a_zh = (f"{nm}（{m['label_zh']} {numx}）是一家<b>{G.esc(ty['zh'])}</b>，于 <b>{d_zh}</b>{m['verb_zh']}。"
                f"截至 {retrieved} 快照，登记状态为<b>「{stzh}」</b>（官方原词 {G.esc(st_raw)}）。")

    # 表格行
    date_lab_en = {"gb": "Incorporated", "sg": "Registered", "au": "Registered", "us_fl": "Filed"}[jur]
    date_lab_zh = {"gb": "注册日期", "sg": "注册日期", "au": "注册日期", "us_fl": "登记日期"}[jur]
    date_val = f"<b>{d_en}</b><span class='raw'>[{G.esc(fd or '')}]</span>"
    rows_en = [("Status", b(sten, G.esc(st_raw)), vurl),
               ("Type", f"{G.esc(ty['en'])}<span class='raw'>[{G.esc(ty_raw)}]</span>", vurl),
               (date_lab_en, date_val, vurl)]
    rows_zh = [("状态", b(stzh, G.esc(st_raw)), vurl),
               ("类型", f"{G.esc(ty['zh'])}<span class='raw'>[{G.esc(ty_raw)}]</span>", vurl),
               (date_lab_zh, date_val, vurl)]
    if jur == "au":
        rows_en.append(("Address", "Official data does not include address", vurl))
        rows_zh.append(("地址", "官方数据不含地址", vurl))
    else:
        if jur == "gb" and ind:
            ind_html = G.esc(ind)                      # '68209 - …' 半角连字符原样
            lab_en, lab_zh = "Industry code (SIC)", "行业代码（SIC）"
        elif jur == "sg" and ind:
            ind_html = f"<code>{G.esc(ind)}</code>"    # SSIC 纯码
            lab_en, lab_zh = "Primary SSIC", "主要行业代码（SSIC）"
        else:
            ind_html, lab_en, lab_zh = "", "Industry", "行业"
        if ind_html:
            rows_en.append((lab_en, ind_html, vurl))
            rows_zh.append((lab_zh, ind_html, vurl))
        if jur == "gb":
            addr_disp = gb_titlecase(addr) if addr else ""
        elif jur == "sg":
            addr_disp = sg_address(addr) if addr else ""
        else:
            addr_disp = addr or ""
        addr_disp = G.esc(addr_disp)
        if addr_disp:
            rows_en.append(("Registered address" if jur != "us_fl" else "Principal address", addr_disp, vurl))
            rows_zh.append(("注册地址" if jur != "us_fl" else "主要地址", addr_disp, vurl))
        if jur == "us_fl":
            ag = fl_agent(agent) if agent else ""
            rows_en.append(("Registered agent", G.esc(ag) if ag else "Not recorded", vurl))
            rows_zh.append(("注册代理人", G.esc(ag) if ag else "未记载", vurl))

    # FAQ（第三问数据驱动）——问句由 build() 统一 esc，这里用原始 name；答案自转义
    reg_site = f"<a href='{vurl}'>{v_en}</a>"
    reg_site_zh = f"<a href='{vurl}'>{v_zh}</a>"
    q1_en, a1_en = f"Is {name} an active company?", (
        f"As of the {retrieved} snapshot, the {m['reg']} register shows it as "
        f"<b>{sten}</b> [{G.esc(st_raw)}] — currently on the register. "
        f"Check the live record at {reg_site}.")
    q1_zh, a1_zh = "它还在营吗？", (
        f"截至 {retrieved} 快照，登记状态为<b>「{stzh}」</b>[{G.esc(st_raw)}]。最新记录请到 {reg_site_zh}核实。")
    q2_en, a2_en = ("When was it registered?" if jur != "us_fl" else "When was it filed?",
                    f"{d_en} ({G.esc(fd or 'unknown')}).")
    q2_zh, a2_zh = "它是什么时候注册的？", f"{d_zh}（{G.esc(fd or '未知')}）。"
    if jur == "gb":
        q3_en = "What industry is it classified under?"
        a3_en = (f"As recorded: <b>{G.esc(ind)}</b> (UK SIC 2007)." if ind
                 else "The register does not record an industry classification for this entity.")
        q3_zh = "它的行业分类是什么？"
        a3_zh = (f"登记原文为 <b>{G.esc(ind)}</b>（UK SIC 2007）。" if ind
                 else "登记记录未记载行业分类。")
    elif jur == "sg":
        q3_en = "What industry code is it classified under?"
        a3_en = (f"SSIC code <b>{G.esc(ind)}</b> on record (code meanings are published by ACRA)." if ind
                 else "The register does not record an SSIC classification for this entity.")
        q3_zh = "它的行业代码是什么？"
        a3_zh = (f"登记的 SSIC 行业代码为 <b>{G.esc(ind)}</b>（代码含义以 ACRA 官方发布为准）。" if ind
                 else "登记记录未记载行业分类。")
    elif jur == "au":
        q3_en = "How is it classified by ASIC?"
        if not ind or ind.startswith("NONE"):
            a3_en = "The register does not record an ASIC classification for this entity."
            a3_zh = "登记记录未记载该实体的 ASIC 分类。"
        else:
            a3_en = (f"Its official ASIC classification on record is <b>{G.esc(ind)}</b> "
                     f"(shown as-is; code meanings are published by ASIC).")
            a3_zh = f"登记记录中的 ASIC 官方分类代码为 <b>{G.esc(ind)}</b>（按原词展示，代码含义以 ASIC 官方发布为准）。"
        q3_zh = "ASIC 是怎么分类它的？"
    else:
        q3_en = "Who is its registered agent?"
        ag = fl_agent(agent) if agent else ""
        a3_en = (f"As registered: <b>{G.esc(ag)}</b> (Sunbiz lists agents surname-first)." if ag
                 else "The register does not record a registered agent for this entity.")
        q3_zh = "它的注册代理人是谁？"
        a3_zh = (f"登记册记录为 <b>{G.esc(ag)}</b>（Sunbiz 官方格式，姓氏在前）。" if ag
                 else "登记记录未记载注册代理人。")

    rid = ("GB-" if jur == "gb" else "SG-" if jur == "sg" else "AU-" if jur == "au" else "US-FL-") + num
    return dict(
        file=f"{dirjur}/{num}.html", jur=jur, urljur=dirjur, slug=num, number=num, rid=rid,
        retrieved=retrieved, gen=f"{SEED} | snapshot {retrieved}",
        title=f"{name} — registry record 登记记录 | VanSiqi",
        desc=(f"Official registry record for {name} ({lab} {num}) — {ty['en']}, status {st['en']}. "
              f"Data from {m['reg']}, snapshot {retrieved}. 官方登记记录（中文对照）。"),
        og_title=f"{name} — official registry record 官方登记记录",
        og_desc=(f"{lab.capitalize()} {num} · {ty['en']} · Status {st['en']}. "
                 f"Data from {m['reg']}, snapshot {retrieved}. 官方登记记录（中文对照）。"),
        name=name, acn_en=acn_en, acn_zh=acn_zh,
        badge_en=st["en"], badge_zh=st["zh"], badge_cls="ok",
        answer_en=a_en, answer_zh=a_zh,
        rows_en=rows_en, rows_zh=rows_zh,
        faq_en=[(q1_en, a1_en), (q2_en, a2_en), (q3_en, a3_en)],
        faq_zh=[(q1_zh, a1_zh), (q2_zh, a2_zh), (q3_zh, a3_zh)],
    )


def main():
    G.PREVIEW = False  # 金丝雀页是生产产物：订阅按钮走主站绝对路由 /monitor
    os.makedirs(OUT, exist_ok=True)
    live_set = set(LIVE)
    # 有界选样：每国只保留哈希最小的 500 个（bisect 有序表，内存恒定）
    keep = {j: [] for j in LIVE}    # 有序 [(hash, num)]，len <= PER_JUR_TOTAL
    scanned = 0
    cur = G.sqlite3.connect(DB).execute(
        "select jurisdiction, company_number, name, status_raw, industry_raw, filing_date "
        "from company")
    for jur, num, name, st, ind, fd in cur:
        scanned += 1
        if jur not in live_set or st != LIVE[jur]:
            continue
        if jur == "gb" and ind and ind.startswith("99999"):
            continue                                   # GB 休眠排除
        if not name or not (8 <= len(name) <= 60) or " " not in name:
            continue
        if any(ch in name for ch in JUNK):
            continue
        if not fd or fd > CUTOFF:
            continue                                   # 登记满 3 年
        h = hashlib.sha256(f"{SEED}|{jur}|{num}".encode()).hexdigest()
        lst = keep[jur]
        if len(lst) < PER_JUR_TOTAL:
            bisect.insort(lst, (h, num))
        elif h < lst[-1][0]:
            bisect.insort(lst, (h, num))
            lst.pop()
        if scanned % 4_000_000 == 0:
            w(f"...{scanned:,} rows")
    w(f"scanned {scanned:,} rows; cutoff {CUTOFF}")

    sel = {}
    for j in LIVE:
        sel[j] = list(keep[j])
        w(f"{j}: selected {len(sel[j])} of candidate pool (hash-smallest {PER_JUR_TOTAL})")

    # 逐国回查所选行的完整字段（确定性：同 seed 同名单）
    list1, list2 = [], []
    built = 0
    con = G.sqlite3.connect(DB)
    for j in LIVE:
        nums = [n for _, n in sel[j]]
        if not nums:
            continue
        qmarks = ",".join("?" * len(nums))
        rows = con.execute(
            f"select company_number, name, status_raw, entity_type_raw, industry_raw, "
            f"filing_date, address, agent, retrieved_at from company "
            f"where jurisdiction=? and company_number in ({qmarks})", (j, *nums)).fetchall()
        by_num = {r[0]: r for r in rows}
        rank = {n: i for i, (_, n) in enumerate(sorted(sel[j]))}
        for num in sorted(nums, key=lambda n: rank[n]):
            num_, name, st_raw, ty_raw, ind, fd, addr, agent, retrieved = by_num[num]
            wave1 = rank[num] < PER_JUR_WAVE1
            (list1 if wave1 else list2).append([j, num, name])
            if not wave1:
                continue                               # wave2 只出名单，暂不生成
            p = build_page(j, num, name, st_raw, ty_raw, ind, fd, addr, agent, retrieved)
            path = os.path.join(OUT, p["file"])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(G.build(p))
            built += 1
        w(f"{j}: wave1 pages done")

    # 名单 CSV（utf-8-sig 方便 Excel 直接打开抽查）
    for fname, data in (("wave1-list.csv", list1), ("wave2-list.csv", list2)):
        with io.open(os.path.join(OUT, fname), "w", newline="", encoding="utf-8-sig") as f:
            cw = csv.writer(f)
            cw.writerow(["jurisdiction", "company_number", "name"])
            cw.writerows(data)

    # sitemap（production canonical，不带 .html）
    dom = "https://vansiqi.com/company"
    for fname, data in (("sitemap-wave1.xml", list1), ("sitemap-wave2.xml", list2)):
        urls = "".join(
            f"<url><loc>{dom}/{JUR_DIR.get(j, j)}/{n}</loc></url>\n" for j, n, _ in data)
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               f"{urls}</urlset>\n")
        with io.open(os.path.join(OUT, fname), "w", encoding="utf-8") as f:
            f.write(xml)

    w(f"wave1 pages: {built}  list1: {len(list1)}  list2: {len(list2)}")
    w("DONE -> " + OUT)


if __name__ == "__main__":
    main()

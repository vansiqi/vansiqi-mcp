# -*- coding: utf-8 -*-
"""检查页生成：AU 最长名 / 最短名 / 随机 各一张（kyb.db 真实数据）。

make_au_page() 即正式批量生成器的 row→页面映射雏形：
状态/类型走字典（字典外 fallback 原词直出），日期 ISO 化双格式，
分类码按 au.yml class_policy 原词展示，NONE/NONE 如实说明未记载。
安全纪律：所有来自 DB 的原词（状态/类型/编号/地址/名）进入 HTML 前一律 esc；
随机页按快照日做确定性抽取（同快照重跑结果一致，不产生漂移文件）。
"""
import hashlib
import io
import os
import sqlite3

from gen_pages import OUT, build, esc, tr

DB = r"d:\S.Q\kyb-mcp-server\data\kyb.db"
ABR = "https://abr.business.gov.au/"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def fmt_en(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def fmt_zh(iso):
    y, m, d = iso.split("-")
    return f"{y} 年 {int(m)} 月 {int(d)} 日"


def make_au_page(r):
    name, num, snap = r["name"], r["company_number"], r["retrieved_at"]
    st = tr("au", "status", r["status_raw"])
    ty = tr("au", "entity_type", r["entity_type_raw"])
    cls = (r["industry_raw"] or "").strip()
    iso = r["filing_date"]
    regd = r["status_raw"] == "REGD"

    # 所有 DB 原词先转义再进 HTML
    e_num, e_st, e_ty, e_cls = esc(num), esc(r["status_raw"]), esc(r["entity_type_raw"]), esc(cls)
    e_st_en, e_st_zh, e_ty_en, e_ty_zh = esc(st["en"]), esc(st["zh"]), esc(ty["en"]), esc(ty["zh"])

    # 日期缺_record如实标注，不编造
    if iso:
        date_en, date_zh, e_iso = esc(fmt_en(iso)), esc(fmt_zh(iso)), esc(iso)
        since_en, since_zh = f"since <b>{date_en}</b>", f"自 <b>{date_zh}</b>起"
        og_year = esc(iso[:4])
        faq2_en, faq2_zh = f"{date_en} ({e_iso}).", f"{date_zh}（{e_iso}）。"
    else:
        date_en, date_zh, e_iso = "unknown", "未知", ""
        since_en, since_zh = "since <b>unknown</b>", "自 <b>未知</b>起"
        og_year = "n/a"
        faq2_en, faq2_zh = "The register does not show a registration date.", "登记记录未记载注册日期。"

    # 徽章：一律只用字典译文（"normal standing" 等后缀为编造术语，已按调研去除）；
    # 颜色按状态语义：正常存续绿，其余（注销/除名/外部管理等）红
    badge_en = st["en"]
    badge_zh = st["zh"]
    badge_cls = "ok" if regd else "bad"

    art = "an" if ty["en"][:1] in "AEIOU" else "a"
    answer_en = (f"{esc(name)} (ACN {e_num}) is {art} <b>{e_ty_en}</b> registered with "
                 f"ASIC {since_en}. As of the {esc(snap)} snapshot the register "
                 f"shows its status as <b>{e_st_en}</b> [{e_st}].")
    answer_zh = (f"{esc(name)}（ACN {e_num}）是一家<b>{e_ty_zh}</b>，{since_zh}在 ASIC 登记在册。"
                 f"截至 {esc(snap)} 快照，登记状态为<b>「{e_st_zh}」</b>（官方原词 {e_st}）。")

    q1_en = (f"Is {name} an active company?" if regd
             else f"What is the register status of {name}?")
    faq1_en = (f"As of the {esc(snap)} snapshot, the ASIC register shows it as <b>{e_st_en}</b> "
               f"[{e_st}] — currently on the register. Check the live record at "
               f"<a href='{ABR}'>ABR ↗</a>.") if regd else (
              f"As of the {esc(snap)} snapshot, the ABR register shows its status as "
              f"<b>{e_st_en}</b> [{e_st}]. Check the live record at <a href='{ABR}'>ABR ↗</a>.")
    faq1_zh = (f"截至 {esc(snap)} 快照，ASIC 登记状态为<b>「{e_st_zh}」</b>[{e_st}]。"
               f"最新记录请到 <a href='{ABR}'>ABR 官网 ↗</a>核实。")

    if cls and cls != "NONE/NONE":
        faq3_en = (f"Its official ASIC classification on record is <b>{e_cls}</b> (shown as-is; "
                   f"code meanings are published by ASIC). The registry also records its type "
                   f"as {e_ty_en} [{e_ty}]. Check <a href='{ABR}'>ABR ↗</a> "
                   f"for the current classification.")
        faq3_zh = (f"登记记录中的 ASIC 官方分类代码为 <b>{e_cls}</b>（按原词展示，代码含义以 ASIC "
                   f"官方发布为准）。登记类型同时记录为「{e_ty_zh}」[{e_ty}]。"
                   f"最新分类请到 <a href='{ABR}'>ABR 官网 ↗</a>核实。")
    else:
        faq3_en = (f"The register does not record an ASIC Class/Sub Class for this entity "
                   f"(the fields show {e_cls or 'no value'}). The registry records its type as "
                   f"{e_ty_en} [{e_ty}]. Check <a href='{ABR}'>ABR ↗</a>.")
        faq3_zh = (f"登记记录未记载该实体的 ASIC Class/Sub Class 分类（字段为 {e_cls or '空'}）。"
                   f"登记类型记录为「{e_ty_zh}」[{e_ty}]。"
                   f"最新分类请到 <a href='{ABR}'>ABR 官网 ↗</a>核实。")

    return dict(
        file=f"au/{num}.html", jur="au", slug=num, number=num, rid=f"AU-{num}",
        retrieved=snap, gen="2026-10-26T00:00:00+08:00",
        title=f"{name} — registry record 登记记录 | VanSiqi",
        desc=(f"Official registry record for {name} (ACN {num}) — {ty['en']}, registered "
              f"{date_en}, status {st['en']}. Data from ASIC; verify at ABR. "
              f"官方登记记录（中文对照）。"),
        og_title=f"{name} — official registry record 官方登记记录",
        og_desc=(f"ACN {num} · {ty['en']} · Registered since {og_year}. Data from ASIC, "
                 f"snapshot {snap}. 官方登记记录（中文对照）。"),
        name=name,
        acn_en=f"{e_ty_en} · ACN <code>{e_num}</code>",
        acn_zh=f"{e_ty_zh} · ACN <code>{e_num}</code>",
        badge_en=badge_en, badge_zh=badge_zh, badge_cls=badge_cls,
        answer_en=answer_en, answer_zh=answer_zh,
        rows_en=[("Status", f"<b>{e_st_en}</b><span class='raw'>[{e_st}]</span>", ABR),
                 ("Type", f"{e_ty_en}<span class='raw'>[{e_ty}]</span>", ABR),
                 ("Registered", f"<b>{date_en}</b><span class='raw'>[{e_iso}]</span>", ABR),
                 ("Address", esc(r["address"] or "Official data does not include address"), ABR)],
        rows_zh=[("状态", f"<b>{e_st_zh}</b><span class='raw'>[{e_st}]</span>", ABR),
                 ("类型", f"{e_ty_zh}<span class='raw'>[{e_ty}]</span>", ABR),
                 ("注册日期", f"<b>{date_zh}</b><span class='raw'>[{e_iso}]</span>", ABR),
                 ("地址", esc(r["address"] or "官方数据不含地址"), ABR)],
        faq_en=[(q1_en, faq1_en),
                ("When was it registered?", faq2_en),
                ("How is it classified by ASIC?", faq3_en)],
        faq_zh=[("它还在营吗？", faq1_zh),
                ("它是什么时候注册的？", faq2_zh),
                ("ASIC 是怎么分类它的？", faq3_zh)],
    )


def pick_random(c, taken):
    """按快照日确定性抽一张（同快照重跑同结果）；撞上已选号则顺延。"""
    tot, = c.execute("select count(*) from company where jurisdiction='au'").fetchone()
    snap, = c.execute("select retrieved_at from company where jurisdiction='au' "
                      "order by retrieved_at desc limit 1").fetchone()
    k = int(hashlib.sha256(snap.encode()).hexdigest()[:12], 16) % tot
    row = c.execute("select * from company where jurisdiction='au' "
                    "order by company_number limit 1 offset ?", (k,)).fetchone()
    while row["company_number"] in taken:
        k = (k + 1) % tot
        row = c.execute("select * from company where jurisdiction='au' "
                        "order by company_number limit 1 offset ?", (k,)).fetchone()
    return row


def main():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    longest = c.execute("select * from company where jurisdiction='au' "
                        "order by length(name) desc, company_number limit 1").fetchone()
    shortest = c.execute("select * from company where jurisdiction='au' "
                         "order by length(name) asc, company_number limit 1").fetchone()
    random_row = pick_random(c, {longest["company_number"], shortest["company_number"]})
    picks = [("longest", longest), ("shortest", shortest), ("random", random_row)]
    files = []
    for label, r in picks:
        p = make_au_page(r)
        path = os.path.join(OUT, p["file"])
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(build(p))
        files.append(path)
        print(f"OK [{label}] {p['file']}  len={len(r['name'])}  "
              f"{r['status_raw']}/{r['entity_type_raw']}/{r['industry_raw'] or '-'}")
    print("DONE ->", OUT)
    return files


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""卫星页生成器 v0（template 1.2 = 1.1 骨架 + 手机端单语言切换；四国许可告示按国注入）。

当前仅用于生成四国测试样张（每国一张，双语，含各自数据许可告示）。
正式批量生成在此骨架上扩展。

输出：d:\\S.Q\\kyb-mcp-server\\render\\preview\\
"""
from __future__ import annotations

import io
import os
import re
import sqlite3
from html import unescape as _unescape

import yaml

OUT = r"d:\S.Q\kyb-mcp-server\render\preview"
DICT_DIR = r"d:\S.Q\kyb-mcp-server\dictionaries"
DB_PATH = r"d:\S.Q\kyb-mcp-server\data\kyb.db"

# 预览模式：订阅按钮指向本地订阅页原型；正式模式（False）指向主站 /monitor
PREVIEW = True

# ── 字典接线：翻译一律查 dictionaries/*.yml，查不到走 fallback（原词直出）──
_D = {}


def load_dict(jur: str) -> dict:
    if jur not in _D:
        with io.open(os.path.join(DICT_DIR, f"{jur}.yml"), encoding="utf-8") as f:
            _D[jur] = yaml.safe_load(f)
    return _D[jur]


def tr(jur: str, kind: str, code: str) -> dict:
    """查字典：返回 {en, zh}。字典外新值走 fallback（原词直出+未翻译标记）。"""
    d = load_dict(jur).get(kind, {})
    hit = d.get(code)
    if hit:
        return dict(hit)
    return {"en": code, "zh": f"{code}（官方码表未收录）"}


_TOT = None


def db_totals():
    """全库活数字：公司总数 + 登记处数（实时 COUNT，数据涨自动跟着变）。模块级缓存一次。"""
    global _TOT
    if _TOT is None:
        c = sqlite3.connect(DB_PATH)
        n, = c.execute("select count(*) from company").fetchone()
        j, = c.execute("select count(distinct jurisdiction) from company").fetchone()
        c.close()
        en = (f"{n / 1e6:.1f}M" if n >= 1_000_000 else f"{n:,}") + f" companies from {j} registries"
        zh = (f"{j} 个登记处、" + (f"{round(n / 10_000)} 万" if n >= 10_000 else f"{n}") + "家公司")
        _TOT = (en, zh)
    return _TOT

# ── 生成白名单：只有用户确认过样张的国家才会被生成（逐张确认流程）──
CONFIRMED_JURS = ("au", "gb", "sg", "us_fl")

# 各国核对链接文字（与 v17 定稿一致：显示登记处名而非通用词）
VERIFY = {
    "gb": ("Companies House ↗", "Companies House ↗"),
    "sg": ("BizFile ↗", "BizFile ↗"),
    "au": ("ABR ↗", "ABR ↗"),
    "us_fl": ("Sunbiz ↗", "Sunbiz ↗"),
}

# 无变化声明文案（表格外的一行，定版状态）
_NOCHANGE = {
    "en": "No changes to this record since the snapshot above.",
    "zh": "快照以来本记录无变化。",
}

# ── 各国许可告示（来源=官方条款调研 2026-10-25；EN 为法律句原文，ZH 为对照翻译）──
LICENSE = {
    "gb": {
        "en": 'Data source: Companies House. Contains public sector information licensed under '
              'the <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">'
              'Open Government Licence v3.0</a>.',
        "zh": '数据来源：Companies House。本页包含受 <a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/">'
              'Open Government Licence v3.0</a> 许可的公共部门信息。',
    },
    "sg": {
        "en": 'Data source: ACRA (Accounting and Corporate Regulatory Authority), accessed on '
              '2026-10-22 from data.gov.sg. Contains information under the '
              '<a href="https://data.gov.sg/open-data-licence">Singapore Open Data Licence v1.0</a>.',
        "zh": '数据来源：新加坡会计与企业管理局（ACRA），经 data.gov.sg 取数于 2026-10-22。'
              '适用 <a href="https://data.gov.sg/open-data-licence">Singapore Open Data Licence v1.0</a>。',
    },
    "au": {
        "en": 'Data source: ASIC / ABR (Australian Business Register), accessed on 2026-10-23. '
              'This is not an official certified extract; data may be out of date — verify at '
              '<a href="https://abr.business.gov.au/">abr.business.gov.au</a>.',
        "zh": '数据来源：澳大利亚证券投资委员会（ASIC）/ ABR，取数于 2026-10-23。本页非官方认证摘录，'
              '数据可能过时——请以 <a href="https://abr.business.gov.au/">abr.business.gov.au</a> 为准。',
    },
    "us_fl": {
        "en": 'Data source: Florida Division of Corporations (Sunbiz), accessed on 2026-10-23. '
              'This is not a certified copy — records are reproduced as-is and may be out of date.',
        "zh": '数据来源：佛罗里达州务司（Sunbiz），取数于 2026-10-23。本页非官方认证副本，'
              '记录照原样转录且可能过时。',
    },
}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;
  color:#1c211e;background:#e9edeb;line-height:1.65;padding:32px 16px}
.paper{max-width:1120px;margin:0 auto;background:#fff;border-radius:6px;
  box-shadow:0 1px 3px rgba(0,0,0,.08);display:grid;grid-template-columns:1fr 1fr;
  overflow-wrap:anywhere}
.cell{padding:26px 30px;display:flex;flex-direction:column;
  border-right:1px solid transparent}
.cell.left{border-right:1px solid #e9edeb}
.cell.sub{padding:0 30px}
.lang-tag{display:inline-block;font-size:12.5px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;border-radius:4px;padding:4px 12px;margin-bottom:16px;align-self:flex-start}
.lt-en{background:#e8f6ee;color:#127a3a}
.lt-zh{background:#e6f3f8;color:#0e7490}
h1{font-size:26px;font-weight:700;letter-spacing:-.01em;line-height:1.3}
.acn{font-size:14px;color:#5f6a64;margin:6px 0 14px}
code{font-family:Consolas,monospace;font-size:13px;background:#f1f4f2;border-radius:4px;padding:1px 6px}
.badge{display:inline-block;font-size:14px;font-weight:600;border-radius:6px;padding:5px 14px;align-self:flex-start}
.ok{background:#e8f6ee;color:#127a3a}
.bad{background:#fdecec;color:#b91c1c}
.answer{font-size:14.5px;color:#3a443f;margin:14px 0 0;padding:13px 15px;background:#f6f8f7;
  border-left:3px solid #16a34a;border-radius:0 8px 8px 0;flex:1}
h2{font-size:13.5px;text-transform:uppercase;letter-spacing:.06em;color:#5f6a64;
  margin:0 0 12px;font-weight:650}
.src{float:right;font-size:12px;font-weight:400;letter-spacing:0;text-transform:none}
table{width:100%;border-collapse:collapse;font-size:14.5px}
th{text-align:left;font-size:12px;font-weight:500;color:#5f6a64;padding:0 8px 7px;
  border-bottom:1px solid #e4e8e6}
th.vc{text-align:right;width:56px}
td{padding:10px 8px;border-bottom:1px solid #f0f3f1;vertical-align:top;height:68px}
td:first-child{color:#5f6a64;width:88px;font-size:13.5px;overflow-wrap:normal}
td.vc{text-align:right;width:56px;white-space:nowrap}
td a.v{color:#5f6a64;text-decoration:none;font-size:12px}
td a.v:hover{color:#127a3a;text-decoration:underline}
.raw{font-family:Consolas,monospace;font-size:12px;color:#5f6a64;margin-top:3px;
  display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
td .val{display:block;max-height:48px;overflow:hidden}
td .val.cl2{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
td .val.nw{display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.muted{color:#5f6a64;font-size:13.5px}
.nochange{font-size:12.5px;color:#127a3a;margin-top:8px}
.nochange:before{content:"✓ ";font-weight:700}
h3.faq{font-size:15px;font-weight:650;margin:16px 0 5px}
.faq-a{font-size:14px;color:#3a443f;margin-bottom:12px}
.hook{font-size:14px;color:#1c211e;padding:0 15px;flex:1;background:#f6f8f7}
.hook.t{padding-top:13px;border-radius:8px 8px 0 0}
.hook.b{padding-bottom:24px;border-radius:0 0 8px 8px}
.hook.b li{margin-bottom:0}
.hook .h-t{font-weight:650;margin-bottom:8px}
.hook ul{margin:0;list-style:none}
.hook li{margin-bottom:7px;padding-left:18px;position:relative}
.hook li:before{content:"→";position:absolute;left:0;color:#16a34a;font-weight:700}
.hook a{color:#127a3a;font-weight:600;text-decoration:none}
.hook a:hover{text-decoration:underline}
a.btn{display:flex;justify-content:center;align-items:center;
  padding:10px 14px;background:#16a34a;color:#fff;border-radius:8px;font-size:14px;
  font-weight:600;text-decoration:none;white-space:nowrap}
a.btn:hover{background:#127a3a}
.ver{max-width:1120px;margin:12px auto 0;text-align:center;font-family:Consolas,monospace;
  font-size:11.5px;color:#5f6a64}
.disc{font-size:12.5px;color:#5f6a64;line-height:1.7}
.disc a{color:#5f6a64;text-decoration:none;margin-right:9px}
.disc a:hover{color:#127a3a;text-decoration:underline}
.license{font-size:11.5px;color:#5f6a64;margin-top:10px}
.license a{color:#127a3a}
.links{padding-top:14px;font-size:13px}
.links a{color:#127a3a;text-decoration:none;margin-right:14px;font-weight:600}
.links a:hover{text-decoration:underline}
.zh{font-family:'PingFang SC','Microsoft YaHei',sans-serif}
.zh h1{font-family:-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif}
.langbar{display:none}
@media(max-width:480px){
  .paper{grid-template-columns:1fr}
  .cell{border-right:none}
  .cell.left{border-bottom:none}
  body[data-lang="zh"] .cell[lang="en"]{display:none}
  body[data-lang="en"] .cell[lang="zh-CN"]{display:none}
  body[data-lang="en"] .raw{display:none}
  .langbar{display:flex;justify-content:flex-end;align-items:center;gap:8px;
    max-width:1120px;margin:0 auto 8px}
  .langbar button{padding:0;font-family:inherit;background:none;border:none;
    font-size:13.5px;font-weight:600;color:#5f6a64;cursor:pointer}
  .langbar button.on{color:#127a3a;text-decoration:underline;text-underline-offset:3px}
  .langbar .lsep{color:#c4ccc7;font-size:12.5px}
  table{display:block}
  thead{display:none}
  tr:first-child{display:none}
  tr{display:block;padding:9px 0;border-bottom:1px solid #f0f3f1}
  tr:last-child{border-bottom:none}
  td{display:block;width:auto;height:auto;padding:1px 0;border-bottom:none}
  td:first-child{width:auto;font-size:12px}
  td.vc{width:auto;text-align:left;padding-top:2px}
  a.btn{white-space:normal;height:auto;padding:10px 14px;line-height:1.4}
}
"""

DISC_EN = ("This page reproduces the official registry record <b>as-is</b>. We are not a government "
           "agency, we make no judgement about any company, and we always link to the official "
           "source — verify there before making decisions.")
DISC_ZH = ("本页如实转录官方登记记录。我们不是政府机构，不对任何公司做可信度评价；所有信息请到"
           "上方官方来源核实后再做决定。")

# 手机端语言切换（仅 ≤480px 生效；桌面 .langbar 为 display:none，版式与定版一致）。
# 初次访问按浏览器语言自动选；记住用户选择；无 JS 时兜底英文（data-lang 写死在 body）。
MOBILE_LANG_JS = (
    '<script>(function(){var d=document.body,k="vsq-lang";'
    'function set(l){d.setAttribute("data-lang",l);'
    'document.getElementById("lb-en").className=l==="en"?"on":"";'
    'document.getElementById("lb-zh").className=l==="zh"?"on":"";'
    'try{localStorage.setItem(k,l)}catch(_){}}'
    'var s=null;try{s=localStorage.getItem(k)}catch(_){}'
    'if(s==="zh"||s==="en")set(s);'
    'else if((navigator.language||"").indexOf("zh")===0)set("zh");else set("en");'
    'document.getElementById("lb-en").addEventListener("click",function(){set("en")});'
    'document.getElementById("lb-zh").addEventListener("click",function(){set("zh")});'
    '})();</script>')


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def head(p):
    return (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{esc(p["title"])}</title>\n'
            f'<meta name="description" content="{esc(p["desc"])}">\n'
            f'<meta name="generator" content="vansiqi template 1.2">\n'
            f'<link rel="canonical" href="https://vansiqi.com/company/{p.get("urljur", p["jur"])}/{esc(p["slug"])}">\n'
            f'<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 32 32\'%3E%3Crect width=\'32\' height=\'32\' rx=\'6\' fill=\'%2316a34a\'/%3E%3Cpath d=\'M16 3 C16 3 7 14 7 20 a9 9 0 0 0 18 0 C25 14 16 3 16 3 Z\' fill=\'white\'/%3E%3Cpath d=\'M12 21 a4.5 4.5 0 0 0 4.5 4.5\' stroke=\'%2316a34a\' stroke-width=\'2\' stroke-linecap=\'round\' fill=\'none\'/%3E%3E%3C/svg%3E">\n'
            f'<meta property="og:title" content="{esc(p["og_title"])}">\n'
            f'<meta property="og:description" content="{esc(p["og_desc"])}">\n'
            f'<meta property="og:type" content="website">\n'
            f'<style>{CSS}</style></head>\n'
            f'<body data-lang="en">\n'
            f'<div class="langbar" role="group" aria-label="Language switch">\n'
            f'  <button type="button" id="lb-en">English</button>\n'
            f'  <span class="lsep" aria-hidden="true">|</span>\n'
            f'  <button type="button" id="lb-zh">中文</button>\n'
            f'</div>\n'
            f'<!-- kyb-record: {p["rid"]} | gen: {p["gen"]} | tpl: 1.2 -->\n\n'
            f'<div class="paper">\n')


def row2(style, en, zh):
    """一个语义行 = 左 EN cell + 右 ZH cell（起点双侧强制对齐，高度差只在本行消化）。"""
    st = f' style="{style}"' if style else ""
    return (f'  <div class="cell sub left"{st} lang="en">\n    {en}\n  </div>\n'
            f'  <div class="cell sub"{st} lang="zh-CN">\n    {zh}\n  </div>\n')


def build(p):
    html = head(p)
    tot_en, tot_zh = db_totals()
    # ── 行1-4 头部：语言标签+主名 / 编号行 / 状态徽章 / 答案框（各自成行，互不推移）──
    html += row2("padding-top:26px",
                 f'<span class="lang-tag lt-en">English</span>\n    <h1>{esc(p["name"])}</h1>',
                 f'<span class="lang-tag lt-zh">中文</span>\n    <h1>{esc(p["name"])}</h1>')
    html += row2(None,
                 f'<div class="acn">{p["acn_en"]}</div>',
                 f'<div class="acn">{p["acn_zh"]}</div>')
    html += row2(None,
                 f'<span class="badge {p.get("badge_cls", "ok")}">{esc(p["badge_en"])}</span>',
                 f'<span class="badge {p.get("badge_cls", "ok")}">{esc(p["badge_zh"])}</span>')
    html += row2("padding-bottom:20px",
                 f'<div class="answer">{p["answer_en"]}</div>',
                 f'<div class="answer">{p["answer_zh"]}</div>')
    # ── 行5 表格（td 68px 固定画布，行内天然对齐）──
    html += pane_table("en", "left", "Registry record",
                       f"Data as of {p['retrieved']}", p["rows_en"],
                       VERIFY[p["jur"]][0])
    html += pane_table("zh-CN", "", "登记记录",
                       f"数据快照于 {p['retrieved']}", p["rows_zh"],
                       VERIFY[p["jur"]][1])
    # ── 行6-11 FAQ：问、答各自成行（问句再长也不影响下一行起点）──
    for i in range(3):
        q_en, a_en = p["faq_en"][i]
        q_zh, a_zh = p["faq_zh"][i]
        if i == 0:
            en = f'<h2>FAQ</h2>\n    <h3 class="faq">{esc(q_en)}</h3>'
            zh = f'<h2 class="zh">常见提问</h2>\n    <h3 class="faq">{esc(q_zh)}</h3>'
            st = "padding-top:26px"
        else:
            en = f'<h3 class="faq">{esc(q_en)}</h3>'
            zh = f'<h3 class="faq">{esc(q_zh)}</h3>'
            st = None
        html += row2(st, en, zh)
        html += row2("padding-bottom:26px" if i == 2 else None,
                     f'<p class="faq-a">{a_en}</p>',
                     f'<p class="faq-a">{a_zh}</p>')
    # ── 行12-15 钩子：标题+三条清单各自成行（灰底框分段拼回一个整框）──
    html += row2("padding-top:26px",
                 '<div class="hook t"><div class="h-t">More on the main site — free:</div></div>',
                 '<div class="hook t"><div class="h-t zh">主站上还有（全部免费）：</div></div>')
    hook_items = [
        ("m", '<a href="/search">Search other companies\' official records</a> — ' + tot_en,
              '<a href="/search">搜索其他公司的官方记录</a>——' + tot_zh),
        ("m", f'<a href="/history/{p["jur"]}/{esc(p["slug"])}">Full change timeline for this company</a> — recorded since Oct 2026',
              f'<a href="/history/{p["jur"]}/{esc(p["slug"])}">本公司完整变动时间线</a>——自 2026 年 10 月起记录'),
        ("b", '<a href="/monitor">Weekly email alerts</a> — know when any company\'s record changes',
              '<a href="/monitor">每周邮件提醒</a>——任何公司记录一变就知道'),
    ]
    for seg, en, zh in hook_items:
        html += row2(None,
                     f'<div class="hook {seg}"><ul>\n      <li>{en}</li>\n    </ul></div>',
                     f'<div class="hook {seg}"><ul>\n      <li>{zh}</li>\n    </ul></div>')
    # ── 行16 订阅按钮（跳转主站该语言的订阅页）──
    # 预览模式：页面在 preview/{jur}/ 子目录，订阅页原型在 preview/ 根 → 须上级相对路径
    base = "../monitor.html" if PREVIEW else "/monitor"
    html += row2("padding-top:16px;padding-bottom:26px",
                 f'<a class="btn" href="{base}?company={p["jur"]}/{esc(p["number"])}&amp;lang=en">Notify me about changes to this company</a>',
                 f'<a class="btn" href="{base}?company={p["jur"]}/{esc(p["number"])}&amp;lang=zh">订阅此公司变动提醒</a>')
    # ── 行17-19 声明 / 许可 / 链接 ──
    lic = LICENSE[p["jur"]]
    html += row2("padding-top:16px",
                 f'<div class="disc">{DISC_EN}</div>',
                 f'<div class="disc zh">{DISC_ZH}</div>')
    html += row2(None,
                 f'<div class="license">{lic["en"]}</div>',
                 f'<div class="license zh">{lic["zh"]}</div>')
    html += row2("padding-bottom:20px",
                 '<div class="links">\n      <a href="/about">About / data sources</a>\n'
                 '      <a href="/privacy">Privacy</a>\n      <a href="/api">API</a>\n'
                 '      <a href="https://github.com/vansiqi/vansiqi-mcp">MCP</a>\n    </div>',
                 '<div class="links zh">\n      <a href="/about">关于我们 / 数据来源</a>\n'
                 '      <a href="/privacy">隐私政策</a>\n      <a href="/api">API</a>\n'
                 '      <a href="https://github.com/vansiqi/vansiqi-mcp">MCP</a>\n    </div>')
    html += (f'</div>\n<div class="ver">Record ID: {esc(p["rid"])} · data as of {esc(p["retrieved"])}'
             f' · template 1.2</div>\n{MOBILE_LANG_JS}\n</body></html>\n')
    return html


# 表格值 title 阈值：纯文本超过此长度的单元格挂 title（悬停看全文）。
# 画布防线不靠字符数估算（全大写/CJK/窄列都会让估算失灵），
# 一律由 CSS 硬钳制：带原词行值钳 1 行、无原词行值钳 2 行，td 恒 68px。
MAX_VAL = 76


def pane_table(lang, cls, h2, src, rows, verify_label):
    html = f'  <div class="cell {cls}" lang="{lang}">\n    <h2>{h2} <span class="src">{src}</span></h2>\n    <table>\n'
    th = ("<tr><th>Field</th><th>Value <span class='raw'>(official)</span></th><th class='vc'>Verify</th></tr>"
          if lang == "en" else
          "<tr><th>字段</th><th>内容 <span class='raw'>(官方原词)</span></th><th class='vc'>核对</th></tr>")
    html += f"    {th}\n"
    for k, v, url in rows:
        muted = ' class="muted"' if k in ("Address", "地址") else ""
        full = re.sub(r"<[^>]+>", "", str(v))
        # title 取纯文本：值里的实体先还原再按属性转义一次，避免 &amp;amp; 双重转义
        tattr = f' title="{esc(_unescape(full))}"' if len(full) > MAX_VAL else ""
        s = str(v)
        if "<span class='raw'>" in s:
            # 值 1 行（省略）+ 原词 1 行 = 68px 预算（剥掉原串自带的闭合标签，防重复 </span>）
            val, raw = s.split("<span class='raw'>", 1)
            v_html = (f'<span class="val nw">{val}</span>'
                      f"<span class='raw'>{raw.removesuffix('</span>')}</span>")
        elif "<" in s:
            # 值含内联标签：块钳 2 行（48px）
            v_html = f'<span class="val">{s}</span>'
        else:
            # 纯文本：真省略号钳 2 行
            v_html = f'<span class="val cl2">{s}</span>'
        link = f'<a class="v" href="{url}">{verify_label}</a>' if url else ""
        html += f"      <tr><td>{esc(k)}</td><td{muted}{tattr}>{v_html}</td><td class='vc'>{link}</td></tr>\n"
    html += f"    </table>\n    <div class=\"nochange{' zh' if lang != 'en' else ''}\">{_NOCHANGE['zh'] if lang != 'en' else _NOCHANGE['en']}</div>\n  </div>\n"
    return html


# ── 四国样张数据（全部来自 kyb.db 真实行）──
PAGES = [
    dict(  # AU BHP
        file="au/004028077.html", jur="au", slug="004028077", number="004028077",
        rid="AU-004028077", retrieved="2026-10-23", gen="2026-10-26T00:00:00+08:00",
        title="BHP GROUP LIMITED (BHP集团) — registry record 登记记录 | VanSiqi",
        desc="Official registry record for BHP GROUP LIMITED (ACN 004028077) — Australian public company, registered 13 August 1885, status Registered. Data from ASIC; verify at ABR. 官方登记记录（中文对照）。",
        og_title="BHP GROUP LIMITED — official registry record 官方登记记录",
        og_desc="ACN 004028077 · Australian public company · Registered since 1885. Data from ASIC, snapshot 2026-10-23. 官方登记记录（中文对照）。",
        name="BHP GROUP LIMITED",
        acn_en="Australian public company · ACN <code>004028077</code>",
        acn_zh="澳大利亚公众公司 · ACN <code>004028077</code>",
        badge_en="Registered", badge_zh="注册在册", badge_cls="ok",
        answer_en="BHP GROUP LIMITED (ACN 004028077) is an <b>Australian public company</b> registered with ASIC since <b>13 August 1885</b>. As of the 2026-10-23 snapshot the register shows its status as <b>Registered</b> [REGD].",
        answer_zh="BHP GROUP LIMITED（ACN 004028077）是一家<b>澳大利亚公众公司</b>，自 <b>1885 年 8 月 13 日</b>起在 ASIC 登记在册。截至 2026-10-23 快照，登记状态为<b>「注册在册」</b>（官方原词 REGD）。",
        rows_en=[("Status", f"<b>{tr('au','status','REGD')['en']}</b><span class='raw'>[REGD]</span>", "https://abr.business.gov.au/"),
                 ("Type", f"{tr('au','entity_type','APUB')['en']}<span class='raw'>[APUB]</span>", "https://abr.business.gov.au/"),
                 ("Registered", "<b>13 August 1885</b><span class='raw'>[1885-08-13]</span>", "https://abr.business.gov.au/"),
                 ("Address", "Official data does not include address", "https://abr.business.gov.au/")],
        rows_zh=[("状态", f"<b>{tr('au','status','REGD')['zh']}</b><span class='raw'>[REGD]</span>", "https://abr.business.gov.au/"),
                 ("类型", f"{tr('au','entity_type','APUB')['zh']}<span class='raw'>[APUB]</span>", "https://abr.business.gov.au/"),
                 ("注册日期", "<b>1885 年 8 月 13 日</b><span class='raw'>[1885-08-13]</span>", "https://abr.business.gov.au/"),
                 ("地址", "官方数据不含地址", "https://abr.business.gov.au/")],
        faq_en=[("Is BHP GROUP LIMITED an active company?",
                 "As of the 2026-10-23 snapshot, the ASIC register shows it as <b>Registered</b> [REGD] — currently on the register. Check the live record at <a href='https://abr.business.gov.au/'>ABR ↗</a>."),
                ("When was it registered?",
                 "13 August 1885 (1885-08-13)."),
                ("How is it classified by ASIC?",
                 "Its official ASIC classification on record is <b>LMSH/LIST</b> (shown as-is; code meanings are published by ASIC). The registry also records its type as Australian public company [APUB]. Check <a href='https://abr.business.gov.au/'>ABR ↗</a> for the current classification.")],
        faq_zh=[("它还在营吗？",
                 "截至 2026-10-23 快照，ASIC 登记状态为<b>「注册在册」</b>[REGD]。最新记录请到 <a href='https://abr.business.gov.au/'>ABR 官网 ↗</a>核实。"),
                ("它是什么时候注册的？",
                 "1885 年 8 月 13 日（1885-08-13）。"),
                ("ASIC 是怎么分类它的？",
                 "登记记录中的 ASIC 官方分类代码为 <b>LMSH/LIST</b>（按原词展示，代码含义以 ASIC 官方发布为准）。登记类型同时记录为「澳大利亚公众公司」[APUB]。最新分类请到 <a href='https://abr.business.gov.au/'>ABR 官网 ↗</a>核实。")],
        total_text_en="24.6M companies from 4 registries", total_text_zh="4 个登记处、2460 万家公司",
    ),
    dict(  # GB ! LTD
        file="gb/08209948.html", jur="gb", slug="08209948", number="08209948",
        rid="GB-08209948", retrieved="2026-10-22", gen="2026-10-26T00:00:00+08:00",
        title="! LTD — registry record 登记记录 | VanSiqi",
        desc="Official registry record for ! LTD (company number 08209948) — active private limited company, incorporated 11 September 2012. Data from Companies House. 官方登记记录（中文对照）。",
        og_title="! LTD — official registry record 官方登记记录",
        og_desc="Company 08209948 · Private limited company · Active since 2012. Data from Companies House, snapshot 2026-10-22. 官方登记记录（中文对照）。",
        name="! LTD",
        acn_en="Private limited company · Company number <code>08209948</code>",
        acn_zh="私人有限公司 · 公司编号 <code>08209948</code>",
        badge_en="Active", badge_zh="正常存续（在营）", badge_cls="ok",
        answer_en="! LTD (company number 08209948) is an <b>active private limited company</b> incorporated at Companies House on <b>11 September 2012</b>. As of the 2026-10-22 snapshot the register shows its status as <b>Active</b>.",
        answer_zh="! LTD（公司编号 08209948）是一家<b>在营的私人有限公司</b>，于 <b>2012 年 9 月 11 日</b>在英国公司登记处注册。截至 2026-10-22 快照，登记状态为<b>「正常存续（在营）」</b>（官方原词 Active）。",
        rows_en=[("Status", f"<b>{tr('gb','status','Active')['en']}</b><span class='raw'>[Active]</span>", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("Type", f"{tr('gb','entity_type','Private Limited Company')['en']}<span class='raw'>[Private Limited Company]</span>", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("Incorporated", "<b>11 September 2012</b><span class='raw'>[2012-09-11]</span>", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("Registered office", "9 Princes Square, Harrogate, England, HG1 1ND", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("Industry code (SIC)", "99999 - Dormant Company", None)],
        rows_zh=[("状态", f"<b>{tr('gb','status','Active')['zh']}</b><span class='raw'>[Active]</span>", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("类型", f"{tr('gb','entity_type','Private Limited Company')['zh']}<span class='raw'>[Private Limited Company]</span>", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("注册日期", "<b>2012 年 9 月 11 日</b><span class='raw'>[2012-09-11]</span>", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("注册地址", "9 Princes Square, Harrogate, England, HG1 1ND", "https://find-and-update.company-information.service.gov.uk/company/08209948"),
                 ("行业码 (SIC)", "99999 - Dormant Company（休眠公司）", None)],
        faq_en=[("Is ! LTD an active company?",
                 "As of the 2026-10-22 snapshot, Companies House shows it as <b>Active</b>. Check the live record at <a href='https://find-and-update.company-information.service.gov.uk/company/08209948'>Companies House ↗</a>."),
                ("When was it incorporated?",
                 "11 September 2012 (2012-09-11)."),
                ("What industry code is it registered under?",
                 "SIC code <b>99999 - Dormant Company</b> (an official Companies House classification meaning the company is not currently trading).")],
        faq_zh=[("它还在营吗？",
                 "截至 2026-10-22 快照，Companies House 登记状态为<b>「正常存续（在营）」</b>。最新记录请到 <a href='https://find-and-update.company-information.service.gov.uk/company/08209948'>Companies House 官网 ↗</a>核实。"),
                ("它是什么时候注册的？",
                 "2012 年 9 月 11 日（2012-09-11）。"),
                ("它登记的行业码是什么？",
                 "SIC 行业码 <b>99999 - Dormant Company</b>（休眠公司；Companies House 官方分类，表示该公司当前无经营活动）。")],
        total_text_en="24.6M companies from 4 registries", total_text_zh="4 个登记处、2460 万家公司",
    ),
    dict(  # SG ACCESS BPO
        file="sg/199202468e.html", jur="sg", slug="199202468e", number="199202468E",
        rid="SG-199202468E", retrieved="2026-10-22", gen="2026-10-26T00:00:00+08:00",
        title="ACCESS BPO PTE. LTD. — registry record 登记记录 | VanSiqi",
        desc="Official registry record for ACCESS BPO PTE. LTD. (UEN 199202468E) — live local company, incorporated 13 May 1992. Data from ACRA via data.gov.sg. 官方登记记录（中文对照）。",
        og_title="ACCESS BPO PTE. LTD. — official registry record 官方登记记录",
        og_desc="UEN 199202468E · Local company · Live since 1992. Data from ACRA, snapshot 2026-10-22. 官方登记记录（中文对照）。",
        name="ACCESS BPO PTE. LTD.",
        acn_en="Local company · UEN <code>199202468E</code>",
        acn_zh="本地公司 · UEN <code>199202468E</code>",
        badge_en="Live company", badge_zh="在营公司", badge_cls="ok",
        answer_en="ACCESS BPO PTE. LTD. (UEN 199202468E) is a <b>live local company</b> registered with ACRA on <b>13 May 1992</b>. As of the 2026-10-22 snapshot the register shows its status as <b>Live company</b>.",
        answer_zh="ACCESS BPO PTE. LTD.（UEN 199202468E）是一家<b>在营的本地公司</b>，于 <b>1992 年 5 月 13 日</b>在 ACRA 注册。截至 2026-10-22 快照，登记状态为<b>「在营公司」</b>（官方原词 Live Company）。",
        rows_en=[("Status", f"<b>{tr('sg','status','Live Company')['en']}</b><span class='raw'>[Live Company]</span>", "https://www.bizfile.gov.sg/"),
                 ("Type", f"{tr('sg','entity_type','Local Company')['en']}<span class='raw'>[Local Company]</span>", "https://www.bizfile.gov.sg/"),
                 ("Incorporated", "<b>13 May 1992</b><span class='raw'>[1992-05-13]</span>", "https://www.bizfile.gov.sg/"),
                 ("Registered address", "8 BURN ROAD, #16-16, TRIVEX, SINGAPORE 369977", "https://www.bizfile.gov.sg/"),
                 ("Industry code (SSIC)", "<code>82999</code> (official ACRA code)", None)],
        rows_zh=[("状态", f"<b>{tr('sg','status','Live Company')['zh']}</b><span class='raw'>[Live Company]</span>", "https://www.bizfile.gov.sg/"),
                 ("类型", f"{tr('sg','entity_type','Local Company')['zh']}<span class='raw'>[Local Company]</span>", "https://www.bizfile.gov.sg/"),
                 ("注册日期", "<b>1992 年 5 月 13 日</b><span class='raw'>[1992-05-13]</span>", "https://www.bizfile.gov.sg/"),
                 ("注册地址", "8 BURN ROAD, #16-16, TRIVEX, SINGAPORE 369977", "https://www.bizfile.gov.sg/"),
                 ("行业码 (SSIC)", "<code>82999</code>（ACRA 官方代码）", None)],
        faq_en=[("Is ACCESS BPO PTE. LTD. an active company?",
                 "As of the 2026-10-22 snapshot, ACRA shows it as a <b>Live company</b>. Check the live record at <a href='https://www.bizfile.gov.sg/'>BizFile ↗</a>."),
                ("When was it incorporated?",
                 "13 May 1992 (1992-05-13)."),
                ("What industry code is it registered under?",
                 "SSIC code <b>82999</b> (the official ACRA industry classification; the description is published by ACRA).")],
        faq_zh=[("它还在营吗？",
                 "截至 2026-10-22 快照，ACRA 登记状态为<b>「在营公司」</b>（官方原词 Live Company）。最新记录请到 <a href='https://www.bizfile.gov.sg/'>BizFile 官网 ↗</a>核实。"),
                ("它是什么时候注册的？",
                 "1992 年 5 月 13 日（1992-05-13）。"),
                ("它登记的行业码是什么？",
                 "SSIC 行业码 <b>82999</b>（ACRA 官方行业分类，描述以 ACRA 官方发布为准）。")],
        total_text_en="24.6M companies from 4 registries", total_text_zh="4 个登记处、2460 万家公司",
    ),
    dict(  # US-FL FLIP THAT REO
        file="us-fl/l16000216990.html", jur="us_fl", urljur="us-fl", slug="l16000216990", number="L16000216990",
        rid="US-FL-L16000216990", retrieved="2026-10-23", gen="2026-10-26T00:00:00+08:00",
        title="FLIP THAT REO LLC — registry record 登记记录 | VanSiqi",
        desc="Official registry record for FLIP THAT REO LLC (document L16000216990) — Florida LLC, filed 30 November 2016, status Inactive. Data from Sunbiz. 官方登记记录（中文对照）。",
        og_title="FLIP THAT REO LLC — official registry record 官方登记记录",
        og_desc="Document L16000216990 · Florida LLC · Filed 2016. Data from Sunbiz, snapshot 2026-10-23. 官方登记记录（中文对照）。",
        name="FLIP THAT REO LLC",
        acn_en="Florida Limited Liability Co. · Document number <code>L16000216990</code>",
        acn_zh="佛罗里达有限责任公司 · 文件号 <code>L16000216990</code>",
        badge_en="Inactive", badge_zh="非活跃（未处于正常存续状态）", badge_cls="bad",
        answer_en="FLIP THAT REO LLC (document number L16000216990) is a <b>Florida limited liability company</b> filed with the Florida Division of Corporations on <b>30 November 2016</b>. As of the 2026-10-23 snapshot the register shows its status as <b>Inactive</b> — the registry's own term, meaning the entity is not in active standing; the record does not state a reason.",
        answer_zh="FLIP THAT REO LLC（文件号 L16000216990）是一家<b>佛罗里达有限责任公司</b>，于 <b>2016 年 11 月 30 日</b>在佛罗里达州务司登记。截至 2026-10-23 快照，登记状态为<b>「非活跃（未处于正常存续状态）」</b>（官方原词 Inactive）；记录本身未说明原因。",
        rows_en=[("Status", f"<b>{tr('us_fl','status','I')['en']}</b><span class='raw'>[I]</span>", "https://search.sunbiz.org/"),
                 ("Type", f"{tr('us_fl','entity_type','FLAL')['en']}<span class='raw'>[FLAL]</span>", "https://search.sunbiz.org/"),
                 ("Filed", "<b>30 November 2016</b><span class='raw'>[2016-11-30]</span>", "https://search.sunbiz.org/"),
                 ("Principal address", "1558 THE 12TH FAIRWAY, WELLINGTON, FL 33414", "https://search.sunbiz.org/"),
                 ("Registered agent", "THOUBBORON, GARY S", "https://search.sunbiz.org/")],
        rows_zh=[("状态", f"<b>{tr('us_fl','status','I')['zh']}</b><span class='raw'>[I]</span>", "https://search.sunbiz.org/"),
                 ("类型", f"{tr('us_fl','entity_type','FLAL')['zh']}<span class='raw'>[FLAL]</span>", "https://search.sunbiz.org/"),
                 ("登记日期", "<b>2016 年 11 月 30 日</b><span class='raw'>[2016-11-30]</span>", "https://search.sunbiz.org/"),
                 ("主营业地址", "1558 THE 12TH FAIRWAY, WELLINGTON, FL 33414", "https://search.sunbiz.org/"),
                 ("注册代理人", "THOUBBORON, GARY S（Sunbiz 官方格式，姓氏在前）", "https://search.sunbiz.org/")],
        faq_en=[("Is FLIP THAT REO LLC an active company?",
                 "No — as of the 2026-10-23 snapshot, the Florida register shows it as <b>Inactive</b> [I]: the entity is not in active standing. The record does not state a reason. Check <a href='https://search.sunbiz.org/'>Sunbiz ↗</a>."),
                ("When was it filed?",
                 "30 November 2016 (2016-11-30)."),
                ("Who is its registered agent?",
                 "As registered: <b>THOUBBORON, GARY S</b> (Sunbiz lists agents surname-first).")],
        faq_zh=[("它还在营吗？",
                 "不在——截至 2026-10-23 快照，佛罗里达登记状态为<b>「非活跃（未处于正常存续状态）」</b>[I]，记录未说明原因。请到 <a href='https://search.sunbiz.org/'>Sunbiz ↗</a>核实。"),
                ("它是什么时候登记的？",
                 "2016 年 11 月 30 日（2016-11-30）。"),
                ("它的注册代理人是谁？",
                 "登记册记录为 <b>THOUBBORON, GARY S</b>（Sunbiz 官方格式，姓氏在前）。")],
    ),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for p in PAGES:
        if p["jur"] not in CONFIRMED_JURS:
            print("SKIP (pending user confirmation)", p["file"])
            continue
        path = os.path.join(OUT, p["file"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(build(p))
        print("OK", p["file"])
    print("DONE ->", OUT)


if __name__ == "__main__":
    main()

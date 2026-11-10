# -*- coding: utf-8 -*-
"""版式压力测试页：把四国「最长/最短」真实公司名灌进定版模板，
验证对称设计在极端数据下依然成立。输出仅作测试用（_test_ 前缀），
不是用户可见页面，不进金丝雀批次。

数据来自 kyb.db 全库极值扫描（2026-10-26）：
  au    len=100  671968059     AGENCE BELGA-...
  au    len=3    625727157     EKO
  gb    len=160  16514020      HOGWARTS ...
  gb    len=1    SL000995      C
  sg    len=100  T21FC0018F    ASOCIACION ...
  sg    len=1    53115120D     0
  us_fl len=192  L02000014055  1 STOP REAL ESTATE, LLC****...
  us_fl len=1    N23000012456  *
另加一张超长地址页，验证表格值截断（td 68px 固定画布保护）。
"""
import io
import os

from gen_pages import OUT, PAGES, build, esc

BASE = {p["jur"]: p for p in PAGES}

FL_LONG = "1 STOP REAL ESTATE, LLC" + "*" * (192 - 23)
LONG_ADDR = ("Level 42, Tower B, 128 Extremely Long Boulevard Extension, "
             "North Corporate Park District, Sydney NSW 2000, Australia, Suite 9012")

CASES = [
    ("au", "long", "671968059",
     "AGENCE BELGA-AGENCE TELEGRAPHIQUE BELGE DE PRESSE, S.A.-AGENTSCHAP "
     "BELGA-BELGISCH PERSTELEGRAAF AGE*"),
    ("au", "short", "625727157", "EKO"),
    ("gb", "long", "16514020",
     "HOGWARTS VISHWAVIDYALAYA/HAKWART PALKALAIKKADLAKAM/UNIVERSITAS HOGWARTENSIS/"
     "JAMIEAT HUJURTIS/HOGWARTS UNIVERSITAT/HOGUWATSU DAIGAKU/UNIVERSIDADE DE HOGWARTS LTD"),
    ("gb", "short", "SL000995", "C"),
    ("sg", "long", "T21FC0018F",
     "ASOCIACION PLATAFORMA DE INNOVACION EN LA INDUSTRIA DEL DEPORTE-"
     "GLOBAL SPORTS INNOVATION CENTER GSIC"),
    ("sg", "short", "53115120D", "0"),
    ("us_fl", "long", "L02000014055", FL_LONG),
    ("us_fl", "short", "N23000012456", "*"),
]


def variant(base, kind, number, name):
    """以该国样张为底，换名换号（正文/FAQ/编号行里的旧名旧号一并替换）。"""
    old_n, old_num = base["name"], base["number"]

    def sub(s):
        return str(s).replace(old_n, name).replace(old_num, number)

    p = dict(base)
    # 目录名取样张 file 的目录段（us-fl），禁止用 DB 码 jur（us_fl）——两者不一致会落错目录
    p.update(
        file=f"{base['file'].split('/')[0]}/_test_{kind}.html", slug=number.lower(), number=number,
        rid=f"{base['rid'].rsplit('-', 1)[0]}-{number}", name=name,
        title=f"{name} — registry record 登记记录 | VanSiqi",
        desc=sub(base["desc"]),
        og_title=f"{name} — official registry record 官方登记记录",
        og_desc=sub(base["og_desc"]),
        acn_en=sub(base["acn_en"]), acn_zh=sub(base["acn_zh"]),
        answer_en=sub(base["answer_en"]), answer_zh=sub(base["answer_zh"]),
        faq_en=[(sub(q), sub(a)) for q, a in base["faq_en"]],
        faq_zh=[(sub(q), sub(a)) for q, a in base["faq_zh"]],
        rows_en=[(k, sub(v), sub(u)) for k, v, u in base["rows_en"]],
        rows_zh=[(k, sub(v), sub(u)) for k, v, u in base["rows_zh"]],
    )
    return p


def write(p):
    path = os.path.join(OUT, p["file"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(build(p))
    print("OK", p["file"])


n = 0
for jur, kind, number, name in CASES:
    write(variant(BASE[jur], kind, number, name))
    n += 1

# 超长地址（合成 127 字符，muted 样式单元格）：验证截断 + td 68px 画布保护
p = dict(BASE["au"])
p["file"] = "au/_test_longaddr.html"
p["rid"] = "AU-004028077-LA"
p["rows_en"] = list(BASE["au"]["rows_en"])
p["rows_zh"] = list(BASE["au"]["rows_zh"])
p["rows_en"][3] = ("Address", esc(LONG_ADDR), "https://abr.business.gov.au/")
p["rows_zh"][3] = ("地址", esc(LONG_ADDR), "https://abr.business.gov.au/")
write(p)
n += 1

# 真实全库最长地址（GB，205 字符，含 & 和 * 脏字符）：kyb.db 实录
GB_LONG_ADDR = ('(1 DIGITAL WORLD 306), 1 OXFORD STREET, M1 4PB PURE MEDIA, 1 OXFORD STREET, '
                '(SUITE/STUDIO, DIGITAL WORLD CENTRE, LOWRY PLAZA), MANCHESTER, '
                '(*OUR PURE MEDIA SUITE & STUDIO IS DIFFERENT LCT), ENGLAND, M1 4PB')
p = variant(BASE["gb"], "longaddr", "16485248", "PURE ENTERPRISE MEDIA LTD")
p["rid"] = "GB-16485248-LA"
p["rows_en"] = list(p["rows_en"])
p["rows_zh"] = list(p["rows_zh"])
p["rows_en"][3] = ("Registered office", esc(GB_LONG_ADDR), p["rows_en"][3][2])
p["rows_zh"][3] = ("注册地址", esc(GB_LONG_ADDR), p["rows_zh"][3][2])
write(p)
n += 1

print("DONE", n, "test pages")

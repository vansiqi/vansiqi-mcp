# -*- coding: utf-8 -*-
"""
build_dist.py — 组装 Cloudflare Pages 部署包 dist/
来源：canary/（200 金丝雀页）+ preview/（4 张定版样张 + monitor + privacy）
sitemap 基址 = https://vansiqi.com（生产 canonical，不带 .html）
"""
import os, shutil, glob

RENDER = os.path.dirname(os.path.abspath(__file__))
CANARY = os.path.join(RENDER, "canary")
PREVIEW = os.path.join(RENDER, "preview")
DIST = os.path.join(RENDER, "dist")
JURS = ["gb", "sg", "au", "us-fl"]
DOM = "https://vansiqi.com"

def main():
    # 1. 清空重建 dist
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    company = os.path.join(DIST, "company")
    os.makedirs(company)

    total_pages = 0
    urls = []  # (jur, num) for sitemap

    # 2. canary 200 页 + preview 定版样张 → dist/company/{jur}/
    for jur in JURS:
        dst_jur = os.path.join(company, jur)
        os.makedirs(dst_jur)
        for src_dir in (os.path.join(CANARY, jur), os.path.join(PREVIEW, jur)):
            if not os.path.isdir(src_dir):
                continue
            for f in sorted(glob.glob(os.path.join(src_dir, "*.html"))):
                num = os.path.splitext(os.path.basename(f))[0]
                shutil.copy2(f, os.path.join(dst_jur, num + ".html"))
                if (jur, num) not in urls:
                    urls.append((jur, num))
                    total_pages += 1

    # 3. monitor / privacy
    shutil.copy2(os.path.join(PREVIEW, "monitor.html"), os.path.join(DIST, "monitor.html"))
    shutil.copy2(os.path.join(PREVIEW, "privacy.html"), os.path.join(DIST, "privacy.html"))

    # 4. index.html 落地页（最小版）
    index_html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VanSiqi — official company registry records 官方登记记录</title>
<meta name="description" content="Official company registry records from 4 registries, in plain language. 官方公司登记记录，人话版。">
<link rel="canonical" href="https://vansiqi.com/">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;
  background:#e9edeb;color:#1c211e;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);max-width:640px;padding:48px 40px;text-align:center}
h1{font-size:26px;letter-spacing:-.01em;margin-bottom:10px}
p{font-size:14.5px;color:#5f6a64;line-height:1.7;margin-bottom:22px}
a{color:#127a3a;font-weight:600;text-decoration:none;margin:0 10px}
a:hover{text-decoration:underline}
.muted{font-size:12.5px;color:#5f6a64;margin-top:18px}
</style></head><body><div class="card">
<h1>VanSiqi</h1>
<p>Official company registry records from 4 registries —<br>
Companies House · ACRA · ASIC · Florida Sunbiz —<br>
reproduced as-is, always linked to the source.<br><br>
官方公司登记记录，如实转录，附官方核对链接。</p>
<div>
<a href="/company/gb/08209948">Sample · 英国样张</a>
<a href="/company/sg/199202468e">Sample · 新加坡</a>
<a href="/company/au/004028077">Sample · 澳洲</a>
<a href="/company/us-fl/l16000216990">Sample · 佛州</a>
</div>
<p class="muted">© VanSiqi · registry data as of snapshot · not affiliated with any government agency</p>
</div></body></html>
"""
    with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(index_html)

    # 5. 404.html（Pages 对未知路径返回 404 状态，杜绝软 404）
    notfound_html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 — Page not found 页面不存在 | VanSiqi</title>
<meta name="robots" content="noindex">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;
  background:#e9edeb;color:#1c211e;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);max-width:640px;padding:48px 40px;text-align:center}
h1{font-size:26px;letter-spacing:-.01em;margin-bottom:10px}
p{font-size:14.5px;color:#5f6a64;line-height:1.7;margin-bottom:22px}
a{color:#127a3a;font-weight:600;text-decoration:none;margin:0 10px}
a:hover{text-decoration:underline}
.muted{font-size:12.5px;color:#5f6a64;margin-top:18px}
</style></head><body><div class="card">
<h1>404 — Page not found 页面不存在</h1>
<p>The page you requested does not exist in our registry snapshot.<br>
您访问的页面不在我们的登记快照中。</p>
<div>
<a href="/">Home 返回首页</a>
<a href="/company/gb/08209948">Sample · 英国样张</a>
</div>
<p class="muted">© VanSiqi · registry data as of snapshot · not affiliated with any government agency</p>
</div></body></html>
"""
    with open(os.path.join(DIST, "404.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(notfound_html)

    # 5.5 主站占位页（钩子链接目标：/about /search /api /history/*）
    # 样式与 index/404 卡片一致；about 有真实内容可收录，其余 noindex + 订阅 CTA。
    PAGE_CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;
  background:#e9edeb;color:#1c211e;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}
.card{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.08);max-width:640px;padding:48px 40px}
h1{font-size:26px;letter-spacing:-.01em;margin-bottom:10px}
h2{font-size:16px;margin:20px 0 8px}
p{font-size:14.5px;color:#3a443f;line-height:1.7;margin-bottom:14px}
.muted{font-size:12.5px;color:#5f6a64;margin-top:18px}
a{color:#127a3a;font-weight:600;text-decoration:none}
a:hover{text-decoration:underline}
ul{margin:0 0 14px 20px;color:#3a443f;font-size:14.5px;line-height:1.8}
.btn{display:inline-block;background:#16a34a;color:#fff;border-radius:8px;padding:10px 18px;margin:4px 0 14px}
.btn:hover{background:#127a3a;text-decoration:none}"""

    about_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>About · 数据来源 | VanSiqi</title>
<meta name="description" content="VanSiqi reproduces official company registry records from Companies House, ACRA, ASIC and Florida Sunbiz, in plain language. 官方登记记录的人话版，附官方核对链接。">
<link rel="canonical" href="https://vansiqi.com/about">
<style>{PAGE_CSS}</style></head><body><div class="card">
<h1>About VanSiqi · 关于我们与数据来源</h1>
<p>We reproduce <b>official company registry records</b> as-is, translate the
registry jargon into plain language, and always link back to the official
source so you can verify before making decisions.</p>
<p>我们如实转录<b>官方公司登记记录</b>，把登记处术语翻译成人话，并提供官方
原始记录核对链接——做决定前请先到官方来源核实。</p>
<h2>Data sources · 数据来源</h2>
<ul>
<li>UK — <a href="https://find-and-update.company-information.service.gov.uk/" rel="nofollow">Companies House</a></li>
<li>Singapore — <a href="https://www.acra.gov.sg/" rel="nofollow">ACRA</a> (via data.gov.sg)</li>
<li>Australia — <a href="https://asic.gov.au/" rel="nofollow">ASIC</a></li>
<li>Florida, US — <a href="https://search.sunbiz.org/" rel="nofollow">Florida Division of Corporations (Sunbiz)</a></li>
</ul>
<h2>What we are not · 我们不是什么</h2>
<p>We are not a government agency. We make no judgement about any company's
trustworthiness. 我们不是政府机构，不对任何公司做可信度评价。</p>
<p><a class="btn" href="/monitor">Get change alerts by email · 订阅变动邮件提醒</a></p>
<p class="muted">© VanSiqi · not affiliated with any government agency · 与任何政府机构无关</p>
</div></body></html>
"""

    search_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Search · 建设中 | VanSiqi</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}</style></head><body><div class="card">
<h1>Full-text search · 全文搜索</h1>
<p><b>Coming soon · 建设中。</b> Site search across all 24.6M registry records
is under construction. 全站搜索功能正在建设中。</p>
<p>Meanwhile, search directly at the official registries:
在此期间，你可以直接到官方登记处查询：</p>
<ul>
<li>UK — <a href="https://find-and-update.company-information.service.gov.uk/" rel="nofollow">Companies House</a></li>
<li>Singapore — <a href="https://www.bizfile.gov.sg/" rel="nofollow">ACRA BizFile</a></li>
<li>Australia — <a href="https://asic.gov.au/online-tools/" rel="nofollow">ASIC Connect</a></li>
<li>Florida, US — <a href="https://search.sunbiz.org/" rel="nofollow">Sunbiz</a></li>
</ul>
<p><a class="btn" href="/monitor">Get change alerts by email · 订阅变动邮件提醒</a></p>
<p class="muted">© VanSiqi · <a href="/">Home 返回首页</a></p>
</div></body></html>
"""

    api_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>API · 建设中 | VanSiqi</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}</style></head><body><div class="card">
<h1>Registry data API · 登记数据 API</h1>
<p><b>Coming soon · 建设中。</b> A small read API over the same registry
snapshot that powers this site. 基于本站同一份登记快照的只读 API 正在建设中。</p>
<p>Want to be notified when it ships? Subscribe to change alerts and you will
hear about it. 想第一时间知道？订阅变动提醒即可。</p>
<p><a class="btn" href="/monitor">Subscribe · 订阅提醒</a></p>
<p class="muted">© VanSiqi · <a href="/">Home 返回首页</a></p>
</div></body></html>
"""

    history_html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Change timeline · 建设中 | VanSiqi</title>
<meta name="robots" content="noindex">
<style>{PAGE_CSS}</style></head><body><div class="card">
<h1>Change timeline · 变动时间线</h1>
<p><b>Coming soon · 建设中。</b> Per-company change timelines (status changes,
address moves, officer updates) are under construction.
每家公司的变动时间线（状态变更、地址迁移、高管变动）正在建设中。</p>
<p>Subscribe to weekly email alerts and you will know the moment any
company's record changes. 订阅每周邮件提醒，任何公司记录一变你就知道。</p>
<p><a class="btn" href="/monitor">Subscribe · 订阅提醒</a></p>
<p class="muted">© VanSiqi · <a href="/">Home 返回首页</a></p>
</div></body></html>
"""

    for name, html in (("about.html", about_html), ("search.html", search_html),
                       ("api.html", api_html), ("history.html", history_html)):
        with open(os.path.join(DIST, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(html)

    # 5.6 _redirects：/history/* 动态路径重写到占位页（200 重写，保 URL 不撞 404）
    with open(os.path.join(DIST, "_redirects"), "w", encoding="utf-8", newline="\n") as f:
        f.write("/history/* /history.html 200\n")

    # 6. robots.txt
    with open(os.path.join(DIST, "robots.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: " + DOM + "/sitemap.xml\n")

    # 6. sitemap.xml（生产 canonical，204 页 + about，不带 .html）
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for jur, num in urls:
        lines.append("<url><loc>%s/company/%s/%s</loc></url>" % (DOM, jur, num))
    lines.append("<url><loc>%s/about</loc></url>" % DOM)
    lines.append("</urlset>")
    with open(os.path.join(DIST, "sitemap.xml"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")

    print("dist rebuilt: %d company pages + index/monitor/privacy/about/search/api/history/404/robots/sitemap/_redirects" % total_pages)

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""卫星页对称自动断言（对称方案第三层：机器测量，不靠人眼）。

对每张页面用 Playwright 实测坐标，断言五条铁律：
  A. 五个语义行（头部/表格/FAQ/钩子/声明）左右 cell 同顶同高
  B. 行内关键元素左右对齐：头部行四件套顶边 + 答案框钉底；
     表格行逐行顶边 + 无变化声明钉底；钩子框顶边 + 按钮钉底；声明顶边 + 链接钉底
  C. 所有 td 高度 = 68px（±1，固定画布未被撑破）
  D. h1 左右行数一致（英文字栈铁律生效）
  E. 无横向溢出

用法：py verify_layout.py page1.html page2.html ...
"""
import os
import sys

from playwright.sync_api import sync_playwright

TOL = 1.5  # px 容差（亚像素取整）

# paper 内 cell 顺序：EN,ZH 交替，两两一行。
# 行结构（19 行）：tag+h1 / 编号 / 徽章 / 答案 / 表格 / Q1 A1 Q2 A2 Q3 A3 / 钩子标题 / 三清单 / 按钮 / 声明 / 许可 / 链接
PAIRS = [(i, i + 1) for i in range(0, 38, 2)]

# (选择器, 比较边)。每个语义行只查其顶部元素与钉底件——起点双侧强制对齐
IN_ROW = {
    0: [(".lang-tag", "top"), ("h1", "top")],          # 语言标签+主名
    2: [(".acn", "top")],                              # 编号行
    4: [(".badge", "top")],                            # 徽章
    6: [(".answer", "top"), (".answer", "bottom")],    # 答案框（flex 等高：顶底都齐）
    8: [("h2", "top"), ("tr:nth-child(1)", "top"), ("tr:nth-child(2)", "top"),
        ("tr:nth-child(3)", "top"), ("tr:nth-child(4)", "top"),
        ("tr:nth-child(5)", "top"), ("tr:nth-child(6)", "top"),
        (".nochange", "bottom")],                      # 表格
    10: [("h2", "top"), ("h3.faq", "top")],            # FAQ 标题+问1
    12: [(".faq-a", "top")],                           # 答1
    14: [("h3.faq", "top")],                           # 问2
    16: [(".faq-a", "top")],                           # 答2
    18: [("h3.faq", "top")],                           # 问3
    20: [(".faq-a", "top")],                           # 答3
    22: [(".hook", "top"), (".h-t", "top")],           # 钩子标题段
    24: [(".hook li", "top")],                         # 清单1
    26: [(".hook li", "top")],                         # 清单2
    28: [(".hook li", "top")],                         # 清单3
    30: [(".btn", "top"), (".btn", "bottom")],         # 订阅按钮
    32: [(".disc", "top")],                            # 声明
    34: [(".license", "top")],                         # 许可
    36: [(".links", "top")],                           # 链接
}

RECTS = """(sel) => Array.from(document.querySelectorAll('.paper > .cell'))
  .map(c => { const el = c.querySelector(sel); return el ? el.getBoundingClientRect() : null; })"""

CELLS = "() => Array.from(document.querySelectorAll('.paper > .cell')).map(c => c.getBoundingClientRect())"

TD_H = "() => Array.from(document.querySelectorAll('td')).map(t => t.getBoundingClientRect().height)"

H1_LINES = """() => Array.from(document.querySelectorAll('h1')).map(h => {
  const r = document.createRange(); r.selectNodeContents(h);
  const tops = new Set(Array.from(r.getClientRects()).filter(x => x.width > 1).map(x => Math.round(x.top)));
  return tops.size;
})"""


def check(path):
    errs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        pg.goto("file:///" + path.replace("\\", "/"))
        pg.wait_for_load_state("networkidle")

        cells = pg.evaluate(CELLS)
        if len(cells) != 38:
            errs.append(f"结构: paper 内 cell 数 {len(cells)} ≠ 38（19 行模板被改动？）")
            b.close()
            return errs
        for L, R in PAIRS:
            cl, cr = cells[L], cells[R]
            if abs(cl["top"] - cr["top"]) > TOL or abs(cl["height"] - cr["height"]) > TOL:
                errs.append(f"A: 行{L // 2 + 1} 左右 cell 不同框 "
                            f"L(top={cl['top']:.1f},h={cl['height']:.1f}) "
                            f"R(top={cr['top']:.1f},h={cr['height']:.1f})")

        for row, sels in IN_ROW.items():
            for sel, edge in sels:
                r = pg.evaluate(RECTS, sel)
                l, rt = r[L], r[R]
                if l is None and rt is None:
                    continue  # 该页无此元素（如 4 行表无第 6 行），跳过
                if l is None or rt is None:
                    errs.append(f"B: 行{row // 2 + 1} {sel} 只在一侧存在")
                    continue
                if abs(l[edge] - rt[edge]) > TOL:
                    errs.append(f"B: 行{row // 2 + 1} {sel} {edge}不齐 "
                                f"L={l[edge]:.1f} R={rt[edge]:.1f}")

        for h in pg.evaluate(TD_H):
            if abs(h - 68) > 1.0:
                errs.append(f"C: td 高度 {h:.1f}px ≠ 68（固定画布被撑破）")
                break

        lines = pg.evaluate(H1_LINES)
        if len(lines) >= 2 and lines[0] != lines[1]:
            errs.append(f"D: h1 行数不一致 EN={lines[0]} ZH={lines[1]}")

        if pg.evaluate("() => document.documentElement.scrollWidth "
                       "> document.documentElement.clientWidth + 1"):
            errs.append("E: 页面横向溢出")
        b.close()
    return errs


if __name__ == "__main__":
    files = [os.path.abspath(f) for f in sys.argv[1:]]
    if not files:
        print("用法: py verify_layout.py page1.html page2.html ...")
        sys.exit(2)
    bad = 0
    for f in files:
        errs = check(f)
        if errs:
            bad += 1
            print(f"FAIL {f}")
            for e in errs:
                print("   ", e)
        else:
            print(f"PASS {f}")
    print(f"\n{len(files) - bad}/{len(files)} PASS")
    sys.exit(1 if bad else 0)

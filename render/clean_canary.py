# -*- coding: utf-8 -*-
"""清理 canary/ 中不在 wave1 名单里的孤儿页"""
import csv, glob, os

RENDER = os.path.dirname(os.path.abspath(__file__))
CANARY = os.path.join(RENDER, "canary")

DIRMAP = {"us_fl": "us-fl"}  # CSV 用 DB 辖区码 us_fl，目录名用 us-fl

alive = set()
with open(os.path.join(CANARY, "wave1-list.csv"), encoding="utf-8") as f:
    for row in csv.reader(f):
        if not row:
            continue
        jur, num = row[0].strip(), row[1].strip()
        jur = DIRMAP.get(jur, jur)
        alive.add(os.path.normpath(os.path.join(CANARY, jur, num + ".html")))

removed, kept = 0, 0
for f in glob.glob(os.path.join(CANARY, "*", "*.html")):
    if os.path.normpath(f) in alive:
        kept += 1
    else:
        print("REMOVE", os.path.relpath(f, CANARY))
        os.remove(f)
        removed += 1

print("kept:", kept, "removed:", removed)

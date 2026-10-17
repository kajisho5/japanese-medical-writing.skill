#!/usr/bin/env python3
"""スキルを配布用にまとめる（標準ライブラリのみ）。dist/ に .skill と .zip を作る（中身は同じ zip 形式）。"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "japanese-medical-writing"
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
for name in ("japanese-medical-writing.skill", "japanese-medical-writing.zip"):
    with zipfile.ZipFile(DIST / name, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SKILL.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith((".pyc", ".tmp")):
                z.write(p, Path("japanese-medical-writing") / p.relative_to(SKILL))
    print(DIST / name)

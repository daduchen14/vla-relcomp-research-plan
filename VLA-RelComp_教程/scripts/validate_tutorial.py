#!/usr/bin/env python3
"""Offline structural acceptance checks for Day 0–14 markdown files."""

from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED_PHRASES = [
    "当日目标", "为什么服务于 VLA-RelComp", "开始前自检", "知识讲义", "最小例子",
    "必读材料", "操作步骤", "预期输出", "真实代码", "常见错误", "止损",
    "时间预算", "最低完成线", "标准完成线", "交付物", "自测题", "参考答案",
    "复试口述", "实测", "静态核验", "估计—未运行", "待用户执行",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tutorial_root", type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    for day in range(15):
        folder = args.tutorial_root / f"day{day:02d}"
        path = folder / "README.md"
        if not path.exists():
            errors.append(f"missing {path}")
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in REQUIRED_PHRASES:
            if phrase not in text:
                errors.append(f"day{day:02d}: missing phrase {phrase}")
        # Day 0-3 intentionally require substantially more scaffolding than later days.
        # Length is only a smoke check; manual audits judge teaching quality.
        if len(text) < (4500 if day <= 3 else 1500):
            errors.append(f"day{day:02d}: too short for required teaching granularity ({len(text)} chars)")
    if errors:
        print("FAIL")
        for error in errors:
            print("-", error)
        raise SystemExit(1)
    print("PASS: Day 0–14 structural requirements found; this does not replace factual/manual review.")


if __name__ == "__main__":
    main()

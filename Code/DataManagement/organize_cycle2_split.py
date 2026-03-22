#!/usr/bin/env python3
"""
把「扁平」的 Cycle2 拆分结果（例如 results/cycle2_split/DAPI 与 KI67）
按文件名里的 block 前缀，整理成与 Cycle1 一致的结构：

  <cycle2_root>/<block>/DAPI/*.tif
  <cycle2_root>/<block>/KI67/*.tif

这样 main.py 拼接时会在每块下看到 DAPI/KI67 子目录，而不会再走 Composite 跳过逻辑。

文件名需以 block 开头，例如：J3_TMAd_Composite_1_DAPI.tif → block=J3
（正则：一行里最先匹配的「字母+数字」前缀，如 A10、J3）

用法（在 Code 根目录 /app 下）:
  python -m tools.organize_cycle2_split \\
    --dapi-dir results/cycle2_split/DAPI \\
    --ki67-dir results/cycle2_split/KI67 \\
    --dest data/Raw_Data/TMAd/Cycle2

Docker:
  python -m tools.organize_cycle2_split \\
    --dapi-dir /results/cycle2_split/DAPI \\
    --ki67-dir /results/cycle2_split/KI67 \\
    --dest /data/Raw_Data/TMAd/Cycle2

可选：--move 用移动代替复制；--dry-run 只打印计划。
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

# TMA 常见块名：A10、J3、F12 等（字母 + 数字）
BLOCK_PREFIX_RE = re.compile(r"^([A-Za-z]+\d+)_")


def infer_block(name: str) -> str | None:
    m = BLOCK_PREFIX_RE.match(name)
    return m.group(1).upper() if m else None


def distribute_channel_dir(
    src_dir: Path,
    dest_cycle2: Path,
    subfolder: str,
    move: bool,
    dry_run: bool,
) -> tuple[int, int]:
    """把 src_dir 下 tif 按 block 分发到 dest_cycle2/<block>/<subfolder>/"""
    if not src_dir.is_dir():
        print("⚠️ 跳过（目录不存在）: %s" % src_dir)
        return 0, 0

    ok, skipped = 0, 0
    tifs = list(src_dir.glob("*.tif")) + list(src_dir.glob("*.tiff"))
    for path in sorted(tifs, key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        block = infer_block(path.name)
        if not block:
            print("  ⚠️ 无法从文件名推断 block，跳过: %s" % path.name)
            skipped += 1
            continue
        out_dir = dest_cycle2 / block / subfolder
        dest = out_dir / path.name
        if dry_run:
            print("  [dry-run] %s → %s/%s/%s" % (path.name, block, subfolder, path.name))
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            if move:
                shutil.move(str(path), str(dest))
            else:
                shutil.copy2(str(path), str(dest))
            print("  ✅ %s → %s/%s/" % (path.name, block, subfolder))
        ok += 1
    return ok, skipped


def main() -> None:
    p = argparse.ArgumentParser(description="将扁平 Cycle2 DAPI/KI67 整理到各 block 目录")
    p.add_argument("--dapi-dir", type=str, required=True)
    p.add_argument("--ki67-dir", type=str, required=True)
    p.add_argument("--dest", type=str, required=True, help="Cycle2 根目录，如 .../TMAd/Cycle2")
    p.add_argument("--move", action="store_true", help="从源目录移动；默认复制")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    dapi = Path(args.dapi_dir).resolve()
    ki67 = Path(args.ki67_dir).resolve()
    dest = Path(args.dest).resolve()

    print("源 DAPI:  %s" % dapi)
    print("源 KI67:  %s" % ki67)
    print("目标根:   %s" % dest)
    print("模式:     %s\n" % ("移动" if args.move else "复制"))

    o1, s1 = distribute_channel_dir(dapi, dest, "DAPI", args.move, args.dry_run)
    o2, s2 = distribute_channel_dir(ki67, dest, "KI67", args.move, args.dry_run)

    print("\n完成: DAPI %d 个, KI67 %d 个; 无法识别 %d + %d 个" % (o1, o2, s1, s2))
    if not args.dry_run and (o1 or o2):
        print(
            "\n若各 block 根目录仍留有未拆分的 Composite 多通道 tif，"
            "拼接会优先识别 DAPI/KI67 子目录；为节省空间可手动删掉或移到备份文件夹。"
        )


if __name__ == "__main__":
    main()

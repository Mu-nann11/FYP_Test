#!/usr/bin/env python3
"""
TMAd Cycle2：把每个 block 目录下的双通道 Composite TIFF 拆成 DAPI/ 与 KI67/，
再交给 fiji 按通道分别拼接。

不要先对 Cycle2 做「整幅 Composite 拼接」再拆通道，否则与后续按通道分层、配准不一致。
流程：Raw_Data/.../Cycle2/<block>/*.tif（多通道 tile）→ 本脚本 → 同 block 下 DAPI/、KI67/ → main.py 拼接。

用法（在 Code 根目录 / Docker 的 /app 下）:
  python -m tools.spit_channel --cycle-dir /data/Raw_Data/TMAd/Cycle2
  python -m tools.spit_channel --cycle-dir D:/.../Code/data/Raw_Data/TMAd/Cycle2
  python -m tools.spit_channel --root D:/.../Code/data --raw-subdir Raw_Data --dataset TMAd --cycle Cycle2

默认：拆分成功后把 block 根目录下的源 Composite 移到同块下的 Composite_source/（未分割原件归档）。
若不要归档、直接删除，加 --remove-sources。

通道顺序：默认认为文件里「第 0 通道 = Ki67、第 1 通道 = DAPI」（与先前写反的情况对齐）。
若你的数据相反，加 --no-swap-dapi-ki67。
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import tifffile as tiff

# 每块内归档未拆分的原始 Composite（与 DAPI/、KI67/ 同级）
COMPOSITE_SOURCE_DIR = "Composite_source"


def split_two_channel(img):
    if img.ndim != 3:
        raise ValueError("不是多通道图: shape=%s" % (img.shape,))
    if img.shape[0] == 2:
        return img[0], img[1]
    if img.shape[-1] == 2:
        return img[..., 0], img[..., 1]
    raise ValueError("需要恰好 2 通道: shape=%s" % (img.shape,))


def split_one_block(
    block_dir: Path,
    dry_run: bool = False,
    remove_sources: bool = False,
    swap_dapi_ki67: bool = True,
) -> tuple[int, int]:
    """
    只处理直接位于 block 根目录下的 .tif（不递归进 DAPI/KI67/Composite_source）。
    返回 (成功文件数, 跳过数)。
    """
    dapi_dir = block_dir / "DAPI"
    ki67_dir = block_dir / "KI67"
    if not dry_run:
        dapi_dir.mkdir(parents=True, exist_ok=True)
        ki67_dir.mkdir(parents=True, exist_ok=True)

    ok, skipped = 0, 0
    tifs = list(block_dir.glob("*.tif")) + list(block_dir.glob("*.tiff"))
    for path in sorted(tifs, key=lambda p: p.name.lower()):
        if path.parent != block_dir:
            continue
        low = path.name.lower()
        if "_dapi" in low or "_ki67" in low:
            skipped += 1
            continue
        try:
            img = tiff.imread(str(path))
            ch1, ch2 = split_two_channel(img)
        except Exception as e:
            print("  跳过 %s: %s" % (path.name, e))
            skipped += 1
            continue
        # 默认 swap：ch0→Ki67, ch1→DAPI（与常见仪器/先前写反一致）
        if swap_dapi_ki67:
            dapi_plane, ki67_plane = ch2, ch1
        else:
            dapi_plane, ki67_plane = ch1, ch2
        base = path.stem
        dapi_path = dapi_dir / ("%s_DAPI.tif" % base)
        ki67_path = ki67_dir / ("%s_KI67.tif" % base)
        if dry_run:
            print("  [dry-run] %s → DAPI/%s , KI67/%s" % (path.name, dapi_path.name, ki67_path.name))
        else:
            tiff.imwrite(str(dapi_path), dapi_plane)
            tiff.imwrite(str(ki67_path), ki67_plane)
            print("  ✅ %s → DAPI/%s , KI67/%s" % (path.name, dapi_path.name, ki67_path.name))
            if remove_sources:
                try:
                    path.unlink()
                    print("     (已删除源文件 %s)" % path.name)
                except OSError as e:
                    print("     ⚠️ 未能删除源文件 %s: %s" % (path.name, e))
            else:
                arch = block_dir / COMPOSITE_SOURCE_DIR
                arch.mkdir(parents=True, exist_ok=True)
                dest = arch / path.name
                if dest.exists():
                    print("     ⚠️ 归档目标已存在，未移动: %s" % dest)
                else:
                    try:
                        shutil.move(str(path), str(dest))
                        print("     (源文件已移至 %s/)" % COMPOSITE_SOURCE_DIR)
                    except OSError as e:
                        print("     ⚠️ 移至 %s 失败: %s" % (COMPOSITE_SOURCE_DIR, e))
        ok += 1
    return ok, skipped


def run_cycle2_split(
    cycle_dir: Path,
    dry_run: bool = False,
    remove_sources: bool = False,
    swap_dapi_ki67: bool = True,
) -> None:
    if not cycle_dir.is_dir():
        raise SystemExit("目录不存在: %s" % cycle_dir)

    subs = sorted(p for p in cycle_dir.iterdir() if p.is_dir())
    if not subs:
        print("⚠️ %s 下没有子目录（block）" % cycle_dir)
        return

    print("📁 Cycle2 拆分: %s（共 %d 个 block 目录）\n" % (cycle_dir, len(subs)))
    total_ok = total_skipped = 0
    for block_dir in subs:
        if block_dir.name in ("DAPI", "KI67", COMPOSITE_SOURCE_DIR):
            continue
        print("[%s]" % block_dir.name)
        o, s = split_one_block(
            block_dir,
            dry_run=dry_run,
            remove_sources=remove_sources,
            swap_dapi_ki67=swap_dapi_ki67,
        )
        total_ok += o
        total_skipped += s
        if o == 0 and s == 0:
            print("  (无顶层 tif)")
        print()
    print("完成: 拆分写入 %d 个源文件, 跳过 %d" % (total_ok, total_skipped))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cycle2 Composite → 按 block 写入 DAPI/ 与 KI67/")
    parser.add_argument("--cycle-dir", type=str, default=None, help="直接指定 .../TMAd/Cycle2 路径")
    parser.add_argument("--root", type=str, default="/data", help="与 --dataset 联用时的根（默认 /data）")
    parser.add_argument(
        "--raw-subdir",
        type=str,
        default="Raw_Data",
        help="Raw 数据子目录名（默认 Raw_Data）",
    )
    parser.add_argument("--dataset", type=str, default="TMAd", help="数据集目录名")
    parser.add_argument("--cycle", type=str, default="Cycle2", help="周期目录名，一般为 Cycle2")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不写文件")
    parser.add_argument(
        "--remove-sources",
        action="store_true",
        help="拆分成功后删除源 Composite；默认改为移到每块下的 Composite_source/",
    )
    parser.add_argument(
        "--no-swap-dapi-ki67",
        action="store_true",
        help="不交换通道：第 1 路→DAPI、第 2 路→KI67（与默认相反）",
    )
    args = parser.parse_args()

    if args.cycle_dir:
        cycle_dir = Path(args.cycle_dir).resolve()
    else:
        cycle_dir = (Path(args.root) / args.raw_subdir / args.dataset / args.cycle).resolve()

    if args.remove_sources and args.dry_run:
        print("⚠️ --remove-sources 与 --dry-run 同时使用时不会删除文件\n")

    run_cycle2_split(
        cycle_dir,
        dry_run=args.dry_run,
        remove_sources=args.remove_sources and not args.dry_run,
        swap_dapi_ki67=not args.no_swap_dapi_ki67,
    )


if __name__ == "__main__":
    main()

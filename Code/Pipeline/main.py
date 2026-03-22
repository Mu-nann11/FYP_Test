from fiji_stitcher.config import load_config, apply_cli_overrides
from fiji_stitcher.logutil import get_logger
from fiji_stitcher.discovery import get_all_level1_directories
from fiji_stitcher.pipeline import process_all_level1_dirs
from fiji_stitcher.outputs import open_single_stitched_result, open_all_stitched_results
from fiji_stitcher.stitching import init_imagej
from fiji_stitcher.ui import timeout_input

from Stitching.crop_stitched_results import crop_all_blocks
from DataManagement.preprocess import run_preprocess, check_data_status, print_status_report

import os
import re
from pathlib import Path


CHANNEL_NAMES = {"DAPI", "HER2", "PR", "ER", "FITC", "Cy3", "Cy5"}


def is_processable_directory(path):
    """
    判断一个目录是否可以直接作为一级处理目录：
    - 直接包含通道子目录
    - 或直接包含 tif/tiff 文件
    """
    if not os.path.isdir(path):
        return False

    try:
        entries = os.listdir(path)
    except Exception:
        return False

    subdirs = [d for d in entries if os.path.isdir(os.path.join(path, d))]
    tif_files = [f for f in entries if f.lower().endswith((".tif", ".tiff"))]

    has_channel_dirs = any(d in CHANNEL_NAMES for d in subdirs)
    has_tif_files = bool(tif_files)

    return has_channel_dirs or has_tif_files


def detect_directory_structure(path):
    """
    检测目录结构类型
    返回:
      ('direct', path) - 当前目录可直接处理
      ('cycle', [cycle_paths]) - 当前目录下包含 Cycle 子目录
      ('sample', [sample_paths]) - 当前目录下包含样本子目录
      ('invalid', None) - 路径无效
      ('unknown', None) - 无法识别
    """
    if not os.path.isdir(path):
        return ("invalid", None)

    try:
        subdirs = sorted(
            [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
        )
        files = os.listdir(path)
    except Exception:
        return ("unknown", None)

    # 1. 当前目录本身就是可处理目录
    if is_processable_directory(path):
        return ("direct", path)

    # 2. 检查是否包含 Cycle 目录
    cycle_dirs = sorted([d for d in subdirs if d.lower().startswith("cycle")])
    if cycle_dirs:
        cycle_paths = [os.path.join(path, d) for d in cycle_dirs]
        return ("cycle", cycle_paths)

    # 3. 检查是否包含样本目录
    # 优先使用内容判断：子目录本身是否可处理
    processable_children = [
        os.path.join(path, d)
        for d in subdirs
        if is_processable_directory(os.path.join(path, d))
    ]
    if processable_children:
        return ("sample", processable_children)

    # 4. 兼容典型 TMA 命名：A10, B3 等
    sample_pattern = re.compile(r"^[A-Z]+\d+$", re.IGNORECASE)
    sample_dirs = [d for d in subdirs if sample_pattern.match(d)]
    if sample_dirs:
        sample_paths = [os.path.join(path, d) for d in sample_dirs]
        return ("sample", sample_paths)

    # 5. 当前目录直接包含 tif 文件，也视作 direct
    tif_files = [f for f in files if f.lower().endswith((".tif", ".tiff"))]
    if tif_files:
        return ("direct", path)

    return ("unknown", None)


def collect_level1_directories_from_input(path, logger):
    """
    根据输入路径自动检测目录结构，并返回真正可处理的一级目录列表。
    支持：
    - 直接目录
    - dataset/Cycle/sample
    - dataset/sample
    - dataset/Cycle/direct
    """
    collected = []

    structure_type, detected_paths = detect_directory_structure(path)
    logger.info("Detected structure for %s: %s", path, structure_type)

    if structure_type == "direct":
        collected.append(path)

    elif structure_type == "sample":
        logger.info("Detected sample structure in %s", path)
        for sample_path in detected_paths:
            logger.info("Add sample directory: %s", sample_path)
            collected.append(sample_path)

    elif structure_type == "cycle":
        logger.info("Detected cycle structure in %s", path)
        for cycle_path in detected_paths:
            cycle_name = os.path.basename(cycle_path)
            logger.info("Inspecting cycle: %s", cycle_name)

            cycle_structure, cycle_detected = detect_directory_structure(cycle_path)
            logger.info(
                "Detected structure inside cycle %s: %s",
                cycle_path,
                cycle_structure
            )

            if cycle_structure == "direct":
                collected.append(cycle_path)

            elif cycle_structure == "sample":
                for sample_path in cycle_detected:
                    logger.info("Add sample directory from cycle %s: %s", cycle_name, sample_path)
                    collected.append(sample_path)

            else:
                logger.warning("Unknown structure inside cycle directory: %s", cycle_path)
                print(f"⚠️ 无法识别 Cycle 目录结构: {cycle_path}")

    elif structure_type == "invalid":
        logger.error("Invalid directory path: %s", path)
        print(f"❌ 路径无效: {path}")

    else:
        logger.error("Unknown directory structure: %s", path)
        print(f"❌ 无法识别目录结构: {path}")

    # 去重并排序，保证顺序稳定
    collected = sorted(set(collected))
    return collected


def run_data_preprocessing(config, logger):
    """
    运行数据预处理流程
    返回: (是否需要继续拼接, 预处理结果)
    """
    preprocess_config = config.get("PREPROCESS", {})
    
    # 如果配置中禁用了预处理，直接返回
    if not preprocess_config.get("AUTO_RUN", True):
        logger.info("Preprocessing is disabled in config")
        return True, None
    
    # 如果只是检查模式，不做预处理
    if preprocess_config.get("CHECK_ONLY"):
        logger.info("Checking data status (--check-data mode)")
        status = check_data_status(Path(config["DEFAULT_ROOT_DIR"]) / config.get("RAW_DATA_DIR_NAME", "Raw_Data"))
        has_issues = print_status_report(status)
        return not has_issues, status
    
    # 获取 Raw_Data 根目录
    raw_data_root = Path(config["DEFAULT_ROOT_DIR"]) / config.get("RAW_DATA_DIR_NAME", "Raw_Data")
    
    if not raw_data_root.exists():
        logger.warning(f"Raw_Data directory not found: {raw_data_root}")
        return True, None
    
    # 先检查数据状态
    status = check_data_status(raw_data_root)
    has_issues = print_status_report(status)
    
    if not has_issues:
        logger.info("All data is already preprocessed")
        return True, None
    
    # 运行预处理
    print("\n" + "=" * 60)
    print("🔧 开始数据预处理...")
    print("=" * 60)
    
    dry_run = preprocess_config.get("DRY_RUN", False)
    results = run_preprocess(raw_data_root, dry_run=dry_run, logger=logger)
    
    print("\n" + "=" * 60)
    print("✅ 预处理完成！")
    if dry_run:
        print("   （以上为 dry-run 预览，实际未执行任何操作）")
    print("=" * 60)
    
    return True, results


def main():
    import sys
    from pathlib import Path
    
    config = apply_cli_overrides(load_config())
    logger = get_logger(config)

    # 支持 --action crop 直接跳过菜单
    if "--action" in sys.argv:
        idx = sys.argv.index("--action")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "crop":
            crop_all_blocks(config)
            print(f"✅ 裁剪完成，输出目录: {config['CROP_OUTPUT_DIR']}")
            return

    # --batch 模式：自动执行批量拼接（跳过菜单）
    is_batch = "--batch" in sys.argv

    logger.info("Program started")

    # ============================================================
    # 数据预处理阶段
    # ============================================================
    should_continue, preprocess_result = run_data_preprocessing(config, logger)
    
    # 如果只是检查模式
    if config.get("PREPROCESS", {}).get("CHECK_ONLY"):
        return
    
    # 如果只是预处理模式（不运行拼接）
    if config.get("PREPROCESS", {}).get("ONLY_PREPROCESS"):
        print("✅ 预处理完成，程序退出（--preprocess-only 模式）")
        return
    
    if not should_continue:
        print("❌ 预处理失败，程序退出")
        return
    
    # ============================================================
    # 图像拼接阶段
    # ============================================================
    logger.info("Initializing ImageJ...")

    try:
        ij = init_imagej(config)
        logger.info("ImageJ initialized")
    except Exception as e:
        logger.exception("ImageJ init failed: %s", e)
        print(f"❌ ImageJ 初始化失败: {e}")
        return

    # 非交互模式或配置了自动裁剪时，跳过菜单直接执行拼接+自动裁剪
    if not config["INTERACTIVE"]:
        # batch 模式：直接执行拼接流程
        pass
    else:
        print("\n" + "=" * 50)
        print("请选择功能:")
        print("1. 预处理 + 拼接所有数据")
        print("2. 仅预处理（不拼接）")
        print("3. 检查数据预处理状态")
        print("4. 仅拼接（跳过预处理）")
        print("5. 打开单个拼接结果")
        print("6. 批量打开所有拼接结果")
        print("7. 批量裁剪拼接结果")
        print("=" * 50)

        choice = timeout_input(
            "请输入功能编号 (1-7，默认1)",
            default="1",
            timeout=10,
            interactive=config["INTERACTIVE"],
        ).strip() or "1"

        # 选项 4-7 需要先初始化 ImageJ
        if choice in ["4", "5", "6", "7"]:
            try:
                ij = init_imagej(config)
                logger.info("ImageJ initialized")
            except Exception as e:
                logger.exception("ImageJ init failed: %s", e)
                print(f"❌ ImageJ 初始化失败: {e}")
                return

        if choice == "1":
            # 预处理已在前面执行
            pass  # 继续执行拼接

        elif choice == "2":
            print("✅ 仅预处理模式，程序退出")
            return

        elif choice == "3":
            # 检查模式已在前面执行
            return

        elif choice == "4":
            print("⚠️ 跳过预处理模式")
            # 继续执行拼接
            pass

        elif choice == "5":
            open_single_stitched_result(config, logger)
            return

        elif choice == "6":
            open_all_stitched_results(config, logger)
            return

        elif choice == "7":
            crop_all_blocks(config)
            print(f"✅ 裁剪完成，输出目录: {config['CROP_OUTPUT_DIR']}")
            return

        else:
            print("输入无效，程序退出")
            return

    # ============================================================
    # 执行拼接（选项 1 和 4）
    # ============================================================
    if config.get("ONLY_LEVEL1"):
        only_level1 = config["ONLY_LEVEL1"]

        if isinstance(only_level1, (list, tuple)):
            level1_dirs = []
            for input_path in only_level1:
                level1_dirs.extend(collect_level1_directories_from_input(input_path, logger))
        else:
            level1_dirs = collect_level1_directories_from_input(only_level1, logger)
    else:
        level1_dirs = get_all_level1_directories(config)

    if not level1_dirs:
        logger.error("No level1 directories found; exit.")
        print("❌ 无可用一级目录，程序退出")
        return

    logger.info("Final level1 directories count: %d", len(level1_dirs))
    for d in level1_dirs:
        logger.info("Level1 directory: %s", d)

    process_all_level1_dirs(level1_dirs, config, ij, logger)

    # ============================================================
    # 自动裁剪（如果配置启用）
    # ============================================================
    logger.info("AUTO_CROP_AFTER_STITCH config value: %s", config.get("AUTO_CROP_AFTER_STITCH", False))
    if config.get("AUTO_CROP_AFTER_STITCH", False):
        print("\n" + "=" * 60)
        print("🔄 拼接完成，自动运行裁剪...")
        print("=" * 60)
        crop_all_blocks(config)
        print(f"✅ 裁剪完成，输出目录: {config['CROP_OUTPUT_DIR']}")


if __name__ == "__main__":
    main()

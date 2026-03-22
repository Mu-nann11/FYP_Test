import argparse
import os
import shutil
import traceback
from pathlib import Path
from Code.Utils.utils import get_logger
from Code.Config.config import config

# 获取统一日志记录器
logger = get_logger("rename_file")

def correct_filename_prefix(folder_path: str):
    """
    修正文件夹内文件的前缀为文件夹名（核心：以文件夹名为标准）
    :param folder_path: 目标文件夹路径
    """
    try:
        folder_name = os.path.basename(folder_path)
        logger.info(f"开始处理文件夹: {folder_name}")
        
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            if os.path.isdir(file_path):
                continue
            
            # 先把双下划线替换成单下划线，统一格式
            filename_clean = filename.replace("__", "_")
            name_parts = filename_clean.split("_")
            if len(name_parts) < 3:
                logger.warning(f"跳过非标准命名文件: {filename}")
                continue
            
            old_prefix = name_parts[0]
            if old_prefix == folder_name:
                logger.debug(f"文件名前缀已正确，跳过: {filename}")
                continue
            
            new_name = f"{folder_name}_{'_'.join(name_parts[1:])}"
            new_file_path = os.path.join(folder_path, new_name)
            
            if os.path.exists(new_file_path):
                logger.warning(f"新文件名已存在，跳过修正: {filename} → {new_name}")
                continue
            
            os.rename(file_path, new_file_path)
            logger.info(f"修正文件名: {filename} → {new_name}")
    except Exception as e:
        logger.error(f"修正文件名失败 {folder_path}: {e}")
        logger.error(traceback.format_exc())

def classify_tma_files(source_dir: str, marker_map: dict):
    """
    将修正后的文件按标记归类到子文件夹（修复双下划线问题）
    :param source_dir: 目标文件夹路径
    :param marker_map: 标记→子文件夹映射
    """
    try:
        folder_name = os.path.basename(source_dir)
        logger.info(f"开始归类 {folder_name} 文件夹文件:")
        
        for filename in os.listdir(source_dir):
            file_path = os.path.join(source_dir, filename)
            if os.path.isdir(file_path):
                continue
            
            # 关键修复：先把双下划线替换成单下划线，再分割
            filename_clean = filename.replace("__", "_")
            name_parts = [part for part in filename_clean.split("_") if part]  # 过滤空字符串
            
            if len(name_parts) < 3:
                logger.warning(f"跳过非标准命名文件: {filename}")
                continue
            
            marker = name_parts[1]
            if marker not in marker_map:
                logger.warning(f"跳过未知标记文件: {filename} (标记: {marker})")
                continue
            
            target_folder = os.path.join(source_dir, marker_map[marker])
            os.makedirs(target_folder, exist_ok=True)
            
            target_path = os.path.join(target_folder, filename)
            if os.path.exists(target_path):
                logger.warning(f"目标文件已存在，跳过归类: {filename}")
                continue
            
            shutil.move(file_path, target_path)
            logger.info(f"归类完成: {filename} → {marker_map[marker]}/")
    except Exception as e:
        logger.error(f"归类文件失败 {source_dir}: {e}")
        logger.error(traceback.format_exc())

def batch_process_folders(root_dir: str, marker_map: dict):
    """
    批量处理根目录下的所有子文件夹（修正文件名+归类）
    :param root_dir: 根目录
    :param marker_map: 标记→子文件夹映射
    """
    try:
        if not os.path.exists(root_dir):
            logger.error(f"根目录不存在: {root_dir}")
            return

        subfolders = [
            os.path.join(root_dir, f) 
            for f in os.listdir(root_dir) 
            if os.path.isdir(os.path.join(root_dir, f))
        ]
        
        if not subfolders:
            logger.warning(f"根目录 {root_dir} 下未找到任何子文件夹！")
            return
        
        logger.info(f"检测到 {len(subfolders)} 个待处理文件夹")
        
        for folder in subfolders:
            correct_filename_prefix(folder)
            classify_tma_files(folder, marker_map)
            logger.info(f"{os.path.basename(folder)} 处理完成！")
    except Exception as e:
        logger.error(f"批量处理文件夹失败: {e}")
        logger.error(traceback.format_exc())

MARKER_FOLDER_MAP = {
    "w1DAPI": "DAPI",
    "w2GFP": "HER2",
    "w3Cy3": "PR",
    "w4Cy5": "ER",
}


def _resolve_process_root(args: argparse.Namespace) -> Path:
    """确定「子文件夹 = 待处理 block」的父目录。"""
    default_root = Path(config.get("DEFAULT_ROOT_DIR", "/data"))
    raw_name = config.get("RAW_DATA_DIR_NAME", "Raw_Data")
    raw_base = default_root / raw_name

    if args.path:
        return Path(args.path).resolve()
    if args.dataset:
        cycle = (args.cycle or "Cycle1").strip()
        return (raw_base / args.dataset.strip() / cycle).resolve()
    return raw_base.resolve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="修正文件名前缀并按通道归类到子文件夹（每个 block 一个子目录）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
在 Code 根目录下执行（Docker 工作目录 /app）：
  # 处理 Raw_Data 下每个数据集目录（TMAd、TMAe 等）
  python -m tools.rename_file

  # 处理 TMAd 的 Cycle1 下各 Block
  python -m tools.rename_file --dataset TMAd --cycle Cycle1

  # 显式指定父目录
  python -m tools.rename_file --path /data/Raw_Data/TMAd/Cycle1
        """,
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="父目录路径：其下每个子文件夹视为一个 block（内含待重命名 tif）",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="数据集名，与 --cycle 联用，拼成 <DEFAULT_ROOT>/<Raw_Data>/<dataset>/<cycle>",
    )
    parser.add_argument(
        "--cycle",
        type=str,
        default="Cycle1",
        help="与 --dataset 联用时的周期子目录名（默认 Cycle1）",
    )

    args = parser.parse_args()
    root_path = _resolve_process_root(args)

    logger.info("=" * 60)
    logger.info("开始批量处理（修正文件名+修复双下划线归类）")
    logger.info("处理父目录: %s", root_path)
    logger.info("=" * 60)

    batch_process_folders(str(root_path), MARKER_FOLDER_MAP)
    logger.info("所有文件夹处理完成！")

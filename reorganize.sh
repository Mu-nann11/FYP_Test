#!/bin/bash
set -e

echo "==> 创建分支 reorganize-code"
git checkout -b reorganize-code 2>/dev/null || git checkout reorganize-code

echo "==> 创建目标文件夹"
mkdir -p Code/Docker Code/Config Code/Stitching Code/Segmentation Code/Analysis Code/DataManagement Code/Pipeline Code/Utils

echo "==> Docker 相关文件"
git mv Dockerfile Code/Docker/
git mv docker-compose.cpu.yml Code/Docker/
git mv docker-compose.gpu.yml Code/Docker/
git mv .dockerignore Code/Docker/

echo "==> 配置文件"
git mv config.py Code/Config/
git mv environment.yml Code/Config/
git mv fiji_config.json Code/fiji_stitcher/

echo "==> 图像拼接"
git mv crop_stitched_results.py Code/Stitching/

echo "==> 分割相关"
git mv segmentation.py Code/Segmentation/
git mv filter_cellpose_by_roi.py Code/Segmentation/

echo "==> 分析相关"
git mv features.py Code/Analysis/
git mv alignment.py Code/Analysis/
git mv compare_qupath.py Code/Analysis/
git mv label_biomarkers.py Code/Analysis/
git mv ring_metrics_trial.py Code/Analysis/
git mv visualize_roi_comparison.py Code/Analysis/

echo "==> 数据管理"
git mv move_file.py Code/DataManagement/
git mv rename_file.py Code/DataManagement/
git mv rename_cycle2_composite.py Code/DataManagement/
git mv organize_channels.py Code/DataManagement/
git mv organize_cycle2_split.py Code/DataManagement/
git mv spit_channel.py Code/DataManagement/

echo "==> 主流程/入口"
git mv main.py Code/Pipeline/
git mv batch_run_all_to_one.py Code/Pipeline/

echo "==> 工具函数"
git mv utils.py Code/Utils/
git mv select_utils.py Code/Utils/
git mv loader.py Code/Utils/

echo ""
echo "==> 完成！目录结构："
find Code/ -type f | sort

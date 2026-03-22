# FYP_Test 毕业设计项目指南

> 生成时间：2026-03-22
> 仓库地址：https://github.com/Mu-nann11/FYP_Test

---

## 1. GitHub 访问信息

- **仓库**: `Mu-nann11/FYP_Test`
- **Personal Access Token**: 见本地 TOOLS.md（不在仓库中存储）
- **Push 方式**（需要写入时）:
  ```bash
  git remote set-url origin https://x-access-token:<TOKEN>@github.com/Mu-nann11/FYP_Test.git
  git push
  git remote set-url origin https://github.com/Mu-nann11/FYP_Test.git  # 用完清理
  ```

---

## 2. 项目目标

构建一套 **组织微阵列（TMA）图像自动化分析流水线**，用于乳腺癌病理切片的定量分析。

**核心流程**：原始 TIF 图像 → 图像拼接 → 裁剪 → 细胞分割 → 通道对齐 → 特征提取 → 免疫组化自动评分

**支持的数据集**：
- **TMAe**：单 cycle（DAPI / HER2 / PR / ER）
- **TMAd**：双 cycle（cycle1: DAPI/HER2/PR/ER + cycle2: DAPI/KI67）

**输出**：
- 每个 block 的细胞级特征 CSV（核面积、通道强度、膜距离等）
- 免疫组化评分（ER/PR 阳性比例、HER2 0/1+/2+/3+、Ki67 增殖指数）
- 分割叠加图（nuclei overlay、Ki67 overlay）

---

## 3. 项目结构与代码功能

```
FYP_Test/
├── Code/
│   ├── Config/                    # 配置管理
│   │   ├── config.py              # 读取 fiji_config.json，提供 crop_root、batch_output_dir 等
│   │   └── environment.yml        # conda 环境定义（Python 3.10 + Cellpose + PyTorch + Fiji）
│   │
│   ├── Pipeline/                  # 主流程
│   │   ├── main.py                # 交互式入口：拼接/裁剪/查看
│   │   └── batch_run_all_to_one.py # 批量处理核心：加载→分割→对齐→特征→评分→输出CSV
│   │
│   ├── Stitching/                 # 图像拼接后处理
│   │   └── crop_stitched_results.py # 裁剪拼接结果，支持单cycle(TMAe)和双cycle(TMAd)
│   │
│   ├── Segmentation/              # 细胞分割
│   │   ├── segmentation.py        # 三种分割方法 + 胞质扩张 + overlay 可视化
│   │   └── filter_cellpose_by_roi.py # 按 ROI 过滤分割结果
│   │
│   ├── Analysis/                  # 特征分析与评分
│   │   ├── features.py            # 核/胞质形态 + 通道强度 + HER2 膜环 + Ki67 hotspot + 自动评分
│   │   ├── alignment.py           # 基于相位相关的通道对齐（消除多 cycle 间位移）
│   │   ├── compare_qupath.py      # 与 QuPath 结果对比验证
│   │   ├── label_biomarkers.py    # 生物标记物标注
│   │   ├── ring_metrics_trial.py  # 膜环指标试验
│   │   └── visualize_roi_comparison.py # ROI 对比可视化
│   │
│   ├── DataManagement/            # 数据整理工具
│   │   ├── rename_file.py         # 批量重命名
│   │   ├── move_file.py           # 文件移动
│   │   ├── organize_channels.py   # 按通道整理
│   │   ├── organize_cycle2_split.py # Cycle2 拆分
│   │   ├── rename_cycle2_composite.py # Cycle2 composite 重命名
│   │   └── spit_channel.py        # 通道分离
│   │
│   ├── Utils/                     # 工具函数
│   │   ├── loader.py              # 数据加载器（读取裁剪后的 TIF，支持 TMAe/TMAd）
│   │   ├── utils.py               # 通用工具（归一化、日志、q90 统计）
│   │   └── select_utils.py        # 选择工具
│   │
│   ├── fiji_stitcher/             # Fiji 拼接集成
│   │   ├── config.py              # 拼接配置（网格、通道、路径）
│   │   ├── discovery.py           # 自动发现待拼接目录
│   │   ├── pipeline.py            # 拼接流程控制
│   │   ├── stitching.py           # ImageJ/Fiji 拼接调用
│   │   ├── outputs.py             # 拼接结果输出
│   │   ├── files.py               # 文件操作
│   │   ├── logutil.py             # 日志工具
│   │   └── ui.py                  # 交互界面
│   │
│   └── Docker/                    # 容器化部署
│       ├── Dockerfile
│       ├── docker-compose.cpu.yml
│       ├── docker-compose.gpu.yml
│       ├── .dockerignore
│       └── README.md              # Docker 部署说明
│
├── Raw_Data/                      # 原始 TIF 图像数据
│   └── TMAd/Cycle1/A3/*.TIF
│
├── fiji_config.json               # 项目配置文件（路径、参数、评分阈值）
└── README.md
```

---

## 4. 各模块详细功能

### 4.1 Config — 配置管理

**文件**: `Code/Config/config.py`

读取项目根目录的 `fiji_config.json`，提供全局配置访问：

| 属性 | 说明 | 默认值 |
|------|------|--------|
| `crop_root` | 裁剪结果根目录 | `/results/crop` |
| `batch_output_dir` | 批量输出目录 | `/results/batch_features` |
| `expansion_distance` | 胞质扩张像素距离 | 15 |

### 4.2 Pipeline — 主流程

#### `main.py` — 交互式入口

4 个功能：
1. **批量拼接**：自动检测目录结构（direct/cycle/sample），调用 Fiji 拼接
2. **打开单个拼接结果**
3. **批量打开拼接结果**
4. **批量裁剪**：调用 `crop_stitched_results.py`

#### `batch_run_all_to_one.py` — 批量分析核心

对每个 block 执行完整流水线：

```
load_block → align_by_shift → segment_nuclei → get_cytoplasm_masks
→ extract_features → score_markers → compute_ki67_index
```

- **BlockProcessor** 类封装处理逻辑
- 支持 `--resume` 断点续跑
- 输出：`all_blocks_cell_features_{dataset}.csv` + `batch_log_{dataset}.csv`

### 4.3 Segmentation — 细胞分割

**文件**: `Code/Segmentation/segmentation.py`

支持三种分割方法：

| 方法 | 函数 | 说明 |
|------|------|------|
| **Cellpose** | `segment_nuclei()` | 基于深度学习，默认 nuclei 模型，支持 GPU |
| **StarDist** | `segment_nuclei_stardist()` | 预训练 `2D_versatile_fluo` |
| **Watershed** | `segment_nuclei_watershed()` | 传统方法：Otsu → 距离变换 → watershed |

**胞质估算**：`get_cytoplasm_masks()` — 基于 `expand_labels` 从核掩膜向外扩张指定像素距离

**可视化**：
- `save_nuclei_overlay()` — 核彩色 + 胞质绿色 + 边缘白色
- `save_ki67_overlay()` — Ki67 阳性绿色 / 阴性红色

### 4.4 Analysis — 特征分析与评分

#### `features.py` — 特征提取

每细胞提取约 40+ 个特征：

**形态学**：
- `nuc_area` — 核面积
- `nuc_eccentricity` — 核偏心率
- `cell_area` — 细胞面积（核+胞质）
- `cyto_area` — 胞质面积
- `cell_to_nuclear_ratio` — 核质比
- `cyto_to_nuc_dist_mean/p90/max_px` — 胞质到核膜距离

**通道强度**（每个通道 HER2/PR/ER/KI67）：
- `*_nuc_mean/max/p90` — 核内强度
- `*_cyto_mean/max/p90` — 胞质内强度
- `HER2_membrane_mean/p90` — HER2 膜环区域强度（专用）

#### `score_markers()` — 免疫组化自动评分

| 标记物 | 评分逻辑 |
|--------|----------|
| **ER/PR** | Otsu 自动阈值 → 阳性比例 → 块级 Positive/Negative |
| **HER2** | 优先膜环均值 → 回退胞质 → 0/1+/2+/3+ 四级评分 |
| **Ki67** | Hotspot 检测（贪婪选种子）→ Hotspot 内 Otsu → 增殖指数 |

#### `alignment.py` — 通道对齐

使用 `cv2.phaseCorrelate` 计算位移向量，对非 DAPI 通道进行仿射变换对齐。位移超过图像 10% 时告警并使用恒等变换。

### 4.5 Stitching — 图像拼接

#### `crop_stitched_results.py`

裁剪拼接结果：
- 自动计算所有通道的最小公共尺寸
- 去除边缘 margin（默认 20px）
- 支持 TMAe（单 cycle）和 TMAd（双 cycle，cycle2 使用相同裁剪窗口）

#### `fiji_stitcher/` — Fiji 集成

通过 `pyimagej` 调用 ImageJ 的 Grid/Collection Stitching 插件，支持：
- 自动发现目录结构
- 多通道、多 cycle 配置
- GPU 加速

### 4.6 DataManagement — 数据整理

| 脚本 | 功能 |
|------|------|
| `rename_file.py` | 批量重命名（支持正则） |
| `move_file.py` | 按规则移动文件 |
| `organize_channels.py` | 按通道名整理到子目录 |
| `organize_cycle2_split.py` | Cycle2 数据拆分 |
| `rename_cycle2_composite.py` | Cycle2 composite 统一命名 |
| `spit_channel.py` | 多通道 TIF 分离为单通道 |

### 4.7 Utils — 工具

- `loader.py`：数据加载器，读取裁剪后的 TIF，处理 16-bit CLAHE 预处理，支持 composite 拆分
- `utils.py`：`normalize_to_uint16()`、`get_logger()`、`q90()` 等
- `CROP_ROOT = Path("/results/crop")` — 容器内路径

---

## 5. Docker 部署

### 环境

- 基础镜像：`mambaorg/micromamba:1.5.10`
- 环境名：`fiji-stitcher`
- Python 3.10 + PyTorch 2.5.1 (CUDA 12.4) + Cellpose + Fiji

### 路径原理

所有命令从**项目根目录**执行：
```bash
docker-compose -f Code/Docker/docker-compose.gpu.yml <command>
```

**Build context**：`context: ../..`（项目根）+ `dockerfile: Code/Docker/Dockerfile`

**Volume 挂载**：
```
../..:/app                          # 项目根 → 容器 /app
../../data:/data                    # 数据
../../results:/results              # 结果
../../fiji_config.json:/app/fiji_config.json  # 配置
```

容器内路径与本地一致：`/app/Code/Pipeline/main.py`

### 常用命令

```bash
# 构建
docker-compose -f Code/Docker/docker-compose.gpu.yml build

# 运行 main.py（交互式拼接/裁剪）
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher python Code/Pipeline/main.py

# 运行批量分析
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher python Code/Pipeline/batch_run_all_to_one.py --dataset TMAe

# 进入容器调试
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher bash

# 强制重新构建（环境变了）
docker-compose -f Code/Docker/docker-compose.gpu.yml build --no-cache
```

---

## 6. 调试记录

### 问题 1：Docker COPY 找不到 environment.yml

**报错**：
```
failed to compute cache key: "/Code/Config/environment.yml": not found
```

**原因**：
- `docker-compose.gpu.yml` 的 `context: .` 相对于 compose 文件所在目录 `Code/Docker/`
- Dockerfile 的 `COPY environment.yml` 在 `Code/Docker/` 下找不到该文件

**修复**：
1. `context: .` → `context: ../..`（项目根目录）
2. 添加 `dockerfile: Code/Docker/Dockerfile`（指定 Dockerfile 相对路径）
3. Dockerfile 中 `COPY environment.yml` → `COPY Code/Config/environment.yml`

### 问题 2：Docker 找不到 Dockerfile

**报错**：
```
failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory
```

**原因**：改了 `context: ../..` 后，Docker 默认在项目根目录找 `Dockerfile`，但文件在 `Code/Docker/`

**修复**：添加 `dockerfile: Code/Docker/Dockerfile`

### 问题 3：容器内找不到 main.py

**报错**：
```
python: can't open file '/app/main.py': [Errno 2] No such file or directory
```

**原因**：
- Volume 挂载 `../..:/app` 后，容器内 `/app` = 项目根目录
- `main.py` 实际位于 `Code/Pipeline/main.py`
- 旧 Dockerfile 的 `COPY . /app` 会把 `Code/Docker/` 的内容（不含代码）复制到 `/app`

**修复**：
1. Dockerfile: `COPY . /app` → `COPY Code/ /app/Code/`
2. Dockerfile CMD: `python main.py` → `python Code/Pipeline/main.py --batch`
3. docker-compose volumes: `.:/app` → `../..:/app`，`./data` → `../../data`，`./results` → `../../results`
4. docker-compose command: `python batch_run_all_to_one.py` → `python Code/Pipeline/main.py --batch`

### 完整修改清单

| 文件 | 修改内容 |
|------|----------|
| `Code/Docker/Dockerfile` | `COPY environment.yml` → `COPY Code/Config/environment.yml` |
| | `COPY . /app` → `COPY Code/ /app/Code/` |
| | CMD 中 `main.py` → `Code/Pipeline/main.py` |
| `Code/Docker/docker-compose.gpu.yml` | `context: .` → `context: ../..` |
| | 添加 `dockerfile: Code/Docker/Dockerfile` |
| | `.:/app` → `../..:/app` |
| | `./data:/data` → `../../data:/data` |
| | `./results:/results` → `../../results:/results` |
| | command 中 `batch_run_all_to_one.py` → `Code/Pipeline/main.py --batch` |
| `Code/Docker/docker-compose.cpu.yml` | 同 gpu.yml 所有修改 |
| | 添加缺失的 command |

---

## 7. 注意事项

1. **始终从项目根目录执行 docker-compose 命令**
2. `data/` 和 `results/` 通过 volume 挂载，确保本地有这两个目录
3. GPU 版需要宿主机安装 NVIDIA Container Toolkit
4. `fiji_config.json` 在项目根目录，`Config/config.py` 通过 `Path(__file__).resolve().parent.parent.parent` 定位它（本地运行时）或通过挂载到 `/app/fiji_config.json`（容器内）
5. `Utils/loader.py` 中 `CROP_ROOT = Path("/results/crop")` 是容器内路径，本地运行时需注意路径一致性
6. Token 有暴露风险，定期更换

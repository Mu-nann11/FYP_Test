# Docker 部署说明

## 目录结构

```
FYP_Test/                          ← 项目根目录
├── Code/
│   ├── Docker/
│   │   ├── Dockerfile
│   │   ├── docker-compose.cpu.yml
│   │   ├── docker-compose.gpu.yml
│   │   └── .dockerignore
│   ├── Config/
│   │   └── environment.yml        ← conda 环境定义
│   ├── Pipeline/
│   │   └── main.py                ← 主入口
│   └── ...
├── fiji_config.json               ← 项目配置（挂载进容器）
├── data/                          ← 数据目录
└── results/                       ← 输出目录
```

## 路径原理

所有 `docker-compose` 命令都从**项目根目录**执行：
```bash
docker-compose -f Code/Docker/docker-compose.gpu.yml <command>
```

### Build Context（构建上下文）

```yaml
build:
  context: ../..                      # 项目根目录
  dockerfile: Code/Docker/Dockerfile  # Dockerfile 相对于 context 的路径
```

- `context: ../..` → 从 `Code/Docker/` 向上两级到项目根 `FYP_Test/`
- Dockerfile 里的 `COPY` 路径都相对于项目根：
  - `COPY Code/Config/environment.yml /tmp/environment.yml`
  - `COPY Code/ /app/Code/`

### Volume Mounts（挂载卷）

```yaml
volumes:
  - ../..:/app                        # 项目根 → 容器 /app
  - ../../data:/data                  # 数据目录
  - ../../results:/results            # 结果目录
  - ../../fiji_config.json:/app/fiji_config.json
```

容器内路径结构与本地一致：`/app/Code/Pipeline/main.py` 对应本地 `Code/Pipeline/main.py`。

### .dockerignore

放在 `Code/Docker/` 下，排除 `.git`、`__pycache__`、`data`、`results` 等，避免把不必要的文件复制进镜像。

## 常用命令

### 构建镜像

```bash
# GPU 版
docker-compose -f Code/Docker/docker-compose.gpu.yml build

# CPU 版
docker-compose -f Code/Docker/docker-compose.cpu.yml build
```

### 运行默认流程

```bash
# GPU（默认执行 batch_run_all_to_one.py）
docker-compose -f Code/Docker/docker-compose.gpu.yml up

# CPU
docker-compose -f Code/Docker/docker-compose.cpu.yml up
```

### 运行指定脚本

```bash
# 运行 main.py
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher python Code/Pipeline/main.py

# 运行 batch_run_all_to_one.py
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher python Code/Pipeline/batch_run_all_to_one.py

# 运行其他模块脚本（例如数据分析）
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher python Code/Analysis/features.py
```

**规则**：脚本路径从项目根算起，即 `Code/模块名/脚本.py`。

### 进入容器调试

```bash
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher \
  micromamba run -n fiji-stitcher bash
```

## 环境依赖

`Code/Config/environment.yml` 定义了 `fiji-stitcher` conda 环境，包含：
- Python 3.12
- cellpose（细胞分割）
- scikit-image, opencv（图像处理）
- pandas, scikit-learn（数据分析）
- 等

修改环境后需要重新 build：
```bash
docker-compose -f Code/Docker/docker-compose.gpu.yml build --no-cache
```

## 注意事项

1. **始终从项目根目录执行命令**，不要 cd 到 `Code/Docker/` 下执行
2. `data/` 和 `results/` 通过 volume 挂载，不会打进镜像，确保本地有这两个目录
3. GPU 版需要宿主机安装 NVIDIA Container Toolkit
4. `fiji_config.json` 在项目根目录，通过 volume 挂载到 `/app/fiji_config.json`，`Config/config.py` 会自动读取

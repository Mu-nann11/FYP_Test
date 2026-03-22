# FYP_Test 上下文文件

> 给下次对话的 AI 看的。包含项目背景、已修复的问题、当前状态。

---

## 项目信息

- **仓库**: https://github.com/Mu-nann11/FYP_Test
- **本地路径**: D:\Try_munan\FYP_Test
- **项目**: TMA（组织微阵列）图像自动化分析流水线（毕业设计）
- **平台**: Windows PowerShell + Docker (GPU)
- **完整文档**: 见仓库 `FYP_PROJECT_GUIDE.md`

---

## 已修复的 Docker 问题

### 问题 1：COPY environment.yml 失败
```
failed to compute cache key: "/Code/Config/environment.yml": not found
```
**原因**: `docker-compose` 的 `context: .` 指向 `Code/Docker/`，找不到根目录的文件
**修复**:
- `context: .` → `context: ../..`
- 添加 `dockerfile: Code/Docker/Dockerfile`

### 问题 2：找不到 Dockerfile
```
failed to read dockerfile: open Dockerfile: no such file or directory
```
**原因**: context 改了之后 Docker 在根目录找 Dockerfile
**修复**: 添加 `dockerfile: Code/Docker/Dockerfile`

### 问题 3：找不到 main.py
```
python: can't open file '/app/main.py': [Errno 2] No such file or directory
```
**原因**: volume `../..:/app` 后 main.py 在 `/app/Code/Pipeline/main.py`
**修复**:
- Dockerfile: `COPY . /app` → `COPY Code/ /app/Code/`
- Dockerfile CMD: `python main.py` → `python Code/Pipeline/main.py`
- compose volumes: `.:/app` → `../..:/app`，`./data` → `../../data`，`./results` → `../../results`
- compose command: `python batch_run_all_to_one.py` → `python Code/Pipeline/main.py --batch`

### 问题 4：找不到 fiji_stitcher 模块
```
ModuleNotFoundError: No module named 'fiji_stitcher'
```
**原因**: `main.py` 直接 `from fiji_stitcher.config`，但 PYTHONPATH 只有 `/app`，找不到 `/app/Code/fiji_stitcher/`
**修复**: `ENV PYTHONPATH=/app` → `ENV PYTHONPATH=/app:/app/Code`

---

## 当前文件状态

### Dockerfile (`Code/Docker/Dockerfile`)
```dockerfile
COPY Code/Config/environment.yml /tmp/environment.yml
ENV PYTHONPATH=/app:/app/Code
COPY Code/ /app/Code/
CMD ["micromamba", "run", "-n", "fiji-stitcher", "python", "Code/Pipeline/main.py", "--batch"]
```

### docker-compose.gpu.yml 关键配置
```yaml
build:
  context: ../..
  dockerfile: Code/Docker/Dockerfile
volumes:
  - ../..:/app
  - ../../data:/data
  - ../../results:/results
command: ["micromamba", "run", "-n", "fiji-stitcher", "python", "Code/Pipeline/main.py", "--batch"]
```

### docker-compose.cpu.yml 同上修改

---

## 运行命令

```powershell
# 从项目根 D:\Try_munan\FYP_Test 执行

# 构建（改了 Dockerfile 后必须加 --no-cache）
docker-compose -f Code/Docker/docker-compose.gpu.yml build --no-cache

# 运行
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher micromamba run -n fiji-stitcher python Code/Pipeline/main.py

# 批量分析
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher micromamba run -n fiji-stitcher python Code/Pipeline/batch_run_all_to_one.py --dataset TMAe

# 调试进容器
docker-compose -f Code/Docker/docker-compose.gpu.yml run --rm fiji-stitcher micromamba run -n fiji-stitcher bash
```

---

## 规则

- **始终从项目根目录执行 docker-compose 命令**
- 容器内路径结构与本地一致：`/app/Code/Pipeline/main.py`
- 改了 Dockerfile 后必须 `build --no-cache`，否则用缓存的旧镜像
- `PYTHONPATH=/app:/app/Code` 同时支持两种 import：
  - `from fiji_stitcher.config`（通过 /app/Code）
  - `from Code.Analysis.alignment`（通过 /app）

---

## 当前状态

- [x] Docker 路径修复完成
- [x] PYTHONPATH 修复完成
- [ ] **下一步**: 问题 4 修复后尚未验证是否跑通，需要 `git pull` + `build --no-cache` + 运行测试

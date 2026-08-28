# Siegfridi 快速启动指南

本指南面向第一次使用的开发者，5 分钟内跑通「克隆 → 装环境 → 启动 → 生成音色 → 测试」。详细背景见 [README.md](README.md)，里程碑与任务见 [立项计划.md](立项计划.md)。

## 1. 前置要求

- Windows 10/11 x64
- Python **3.11.x**（POC 阶段固定，勿用 3.12——Basic Pitch 依赖的 TensorFlow 2.14 无 3.12 wheel）
- Git
- FluidSynth 原生运行时（仅合成/渲染需要，见第 4 步）

## 2. 克隆与虚拟环境

```powershell
git clone https://github.com/SgfKrc/Siegfiridi.git
cd Siegfiridi

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip 'setuptools<81' wheel
```

## 3. 安装依赖

按用途选择，可叠加：

```powershell
# 最简：仅基础 + 开发工具链（pytest / ruff）
python -m pip install -e ".[dev]"

# 全量：包含 audio、transcription、synthesis、打包与测试覆盖率
python -m pip install -e ".[all]"
```

也可用一键脚本（含 Python 预检、创建 venv、装依赖、跑版本检查与测试）：

```powershell
.\scripts\setup-env.ps1 -All
```

## 4. 安装 FluidSynth 运行时（合成/渲染需要）

pyFluidSynth 会从 `C:\tools\fluidsynth\bin` 自动加载 `libfluidsynth-3.dll`（也支持 `SIEGFRIDI_FLUIDSYNTH` / `SIEGFRIDI_FLUIDSYNTH_DIR` 环境变量覆盖）。本机无包管理器时，从官方 GitHub release 下载 Windows 预编译包解压到该目录：

```powershell
# 解压 fluidsynth-v2.6.0-win10-x64-cpp11.zip 后，将内部目录改为:
#   C:\tools\fluidsynth\
#   其下应有 bin\fluidsynth.exe 与 bin\libfluidsynth-3.dll
```

验证：

```powershell
C:\tools\fluidsynth\bin\fluidsynth.exe --version
python -c "import fluidsynth; print('ok')"
```

## 5. 启动应用

```powershell
python -m siegfridi --version      # 版本检查
python -m siegfridi                # 打开主窗口
```

无桌面环境或做冒烟测试：

```powershell
.\scripts\run-dev.ps1 -Offscreen
```

## 6. 生成原创音色（本机开发可选）

发行构建会自动执行，本机可手动生成项目原创 CC0 东方/黑暗哥特音色包：

```powershell
python scripts\build-oriental-pack.py --output assets\packs\oriental-project-v0.1.sf2 --manifest assets\packs\oriental-project-v01.json
python scripts\build-gothic-pack.py    --output assets\packs\dark-gothic-v0.1.sf2     --manifest assets\packs\dark-gothic-v01.json
```

运行 GUI 需要至少一个可加载音色包。GM 回退包可用脚本获取（约 148 MB，不入库）：

```powershell
.\scripts\fetch-soundfont.ps1
```

## 7. 运行测试

```powershell
python -m pytest -q                       # 全量
python -m pytest tests/test_gui_scenarios.py -q   # GUI 专项
python -m pytest --cov=siegfridi --cov-report=term   # 覆盖率
```

## 8. 打包（可选，需 `.[all]`）

```powershell
.\scripts\build.ps1         # Windows onedir 便携包
.\scripts\build.ps1 -Clean  # 清理旧 build/dist
# 产物 dist/Siegfridi/，冒烟命令：
dist\Siegfridi\Siegfridi.exe --version
```

## 常见问题

- **`Couldn't find the FluidSynth library`**：未装第 4 步的运行时，或 `C:\tools\fluidsynth\bin` 下缺少 `libfluidsynth-3.dll`。
- **TensorFlow 导入报 `_ARRAY_API not found`**：numpy 版本需 `<2`（本项目已固定），勿手动升级。
- **GUI 窗口闪退/无显示**：用 `run-dev.ps1 -Offscreen` 或检查是否安装了 PySide6。
- **音色包哈希校验失败**：本地 SF2 与 `assets/packs/*.json` 清单不符，重新运行对应 fetch/build 脚本。

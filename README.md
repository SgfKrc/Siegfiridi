# Siegfridi

Siegfridi 是一个 Python-first 的 Windows MIDI 编曲工具，优先服务定制化音轨生产，而不是先做通用 DAW 或完整 GM 音源。

一期的音乐方向以东方 Project 风格参考、以《恶魔城》《神之亵渎》为坐标的黑暗哥特风，以及 RPG Maker / BLACK SOULS I-II 语境下的复古 RPG 音轨为审美坐标。参考作品只用于描述风格特征，不复制其旋律、采样、工程文件或其他受保护素材。项目专用音色包、`SoundProfile` 和风格模板与 MIDI 工程分离，方便在不改音符的情况下切换配器。

> 首次上手请直接看 **[QUICKSTART.md](QUICKSTART.md)**：克隆 → 装环境 → 启动 → 生成音色 → 测试，5 分钟跑通。

## 当前状态

P3 音频转录管线已可实际运行：环境固定为 `numpy<2`、TensorFlow 2.14、Basic Pitch 0.4，并已用合成三音符 WAV 实测生成 3 个候选音符。P4 已接入 SoundFont 清单/哈希校验、FluidSynth CLI 渲染和 pyFluidSynth 原生绑定兜底，并登记了 MIT 许可的 FluidR3_GM 3.1 GM 回退包；项目原创 CC0 东方风格和黑暗哥特风格 SF2 均已生成并可试听。P5 已提供 PyInstaller Windows onedir 构建，自动收集 FluidSynth 原生运行文件并生成包哈希清单。

## 开发环境

- Windows 10/11 x64
- Python 3.11.x（POC 阶段固定版本）
- Git

创建虚拟环境并安装开发依赖：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

运行版本检查或启动最小窗口：

```powershell
python -m siegfridi --version
python -m siegfridi
```

开发态查看前端（无需打包）：

```powershell
.\scripts\run-dev.ps1
# 无桌面环境或用于烟测：
.\scripts\run-dev.ps1 -Offscreen
```

窗口中的钢琴卷帘支持添加、移动、缩放和删除音符；左侧钢琴键盘标识音高，顶部 tick 标尺和金色播放游标同步定位，标尺/键盘区域为只读。工作区提供 Dark Gothic、High Contrast、Quiet Light 三套 UI 主题，以及背景图 Cover/Fit、透明度、可读性保护强度和恢复默认；这些界面偏好通过 QSettings 持久化。左侧可切换风格、节拍和本地运行时 SoundFont，并将当前工程试听渲染到 `.siegfridi/preview.wav`。工程可保存为原生 `.siegfridi` 文件，自动生成 `.siegfridi/autosave.siegfridi`，再次保存会轮换 `.bak` 备份；播放支持暂停、恢复、停止和 tick 定位，并可编辑轨道音量/声像。导入音频后由独立 Basic Pitch 进程生成候选轨，可调置信度阈值和量化网格，确认后才写入工程；失败与取消记录到 `.siegfridi/transcription.log`。工具栏和播放控件提供快捷键/悬停提示，文件选择、播放、转录和无选中轨道等结果统一显示在非模态状态栏中。当前已加入可再分发的原创 CC0 东方风格包 `oriental-project-v01.json` 和黑暗哥特包 `dark-gothic-v01.json`；THFont/NeoTHFont/ZUNpet 等社区参考包保留为本地研究资产，不进入发行构建。

GUI 专项测试与覆盖率：

```powershell
python -m pytest tests/test_gui_scenarios.py -q
coverage run -m pytest tests/test_app.py tests/test_gui_scenarios.py -q
coverage report --include="src/siegfridi/app/*" -m
```

视觉基准检查（桌面/浅色/窄屏、无 MIDI 输出设备和高 DPI 冒烟）以及人工检查清单见 [`VISUAL_CHECKLIST.md`](VISUAL_CHECKLIST.md)：

```powershell
python scripts/check-gui-visual.py --output-dir .siegfridi\visual\n7-005
python scripts/check-gui-visual.py --output-dir .siegfridi\visual\n7-005-hidpi --scale-factor 1.25
```

完整测试质量审计记录和覆盖率基线见 [`TEST_AUDIT.md`](TEST_AUDIT.md)。全量质量门禁命令为 `coverage run -m pytest -q; coverage report -m`，源码语句覆盖率低于 80% 时报告失败。

音频、转录和合成依赖按需安装：`.[audio]`、`.[transcription]`、`.[synthesis]`。发布版会通过 PyInstaller 生成 Windows 安装包，并附第三方许可证、模型和音色包来源清单。

构建 Windows 便携包（需要已安装 `.[all]`）：

```powershell
.\scripts\build.ps1
# 需要清理旧 build/dist 时：
.\scripts\build.ps1 -Clean
```

产物位于 `dist/Siegfridi/`，启动冒烟命令为 `dist/Siegfridi/Siegfridi.exe --version`。构建脚本会从 `SIEGFRIDI_FLUIDSYNTH_DIR` 或 `C:\tools\fluidsynth\bin` 收集 CLI/DLL；SoundFont、模型和录音素材不会因构建自动取得授权，必须通过各自清单导入。

发行构建会先运行 `scripts/build-oriental-pack.py` 和 `scripts/build-gothic-pack.py` 生成原创 CC0 音色，再由清单白名单收集；`local-study-only` 社区参考包不会进入 `dist/`。

获取已核验的 GM 回退音色（约 148 MB，本地文件按 `.gitignore` 排除）：

```powershell
.\scripts\fetch-soundfont.ps1
```

该脚本固定 FluidR3_GM v3.1 的下载地址和 SHA-256，并保存 MIT/COPYING 与来源说明；它只提供 GM 基线，不替代项目专用东方 Project / 黑暗哥特音色包。

获取已核验的 CC0 东方竹笛源素材（约 7 MB，SFZ/WAV，当前仅作制作源素材）：

```powershell
.\scripts\fetch-oriental-source.ps1
```

该脚本固定 [SP Bamboo Flute](https://github.com/NeoSoundFonts/SP-Bamboo-Flute) 的提交版本和归档 SHA-256；源包的 41 个文件哈希、许可证和“尚不可直接渲染”状态记录在 `assets/packs/sp-bamboo-flute-source.json`。转换为 SF2 后必须生成新的运行时清单和哈希，不能沿用源归档哈希。

获取已核验的 CC0 FreePats Ocarina SF2（约 3.2 MB，本地文件按 `.gitignore` 排除）：

```powershell
python -m pip install -e ".[assets]"
.\scripts\fetch-freepats-ocarina.ps1
```

脚本固定 2024-10-02 归档和 SF2 SHA-256，并复制 CC0 文本与录音来源说明；该包可以直接被 FluidSynth 加载，但只提供单一风笛音色，不能替代项目专用东方/黑暗哥特音色包。

### 东方风格音源边界

东方的辨识度不等于某一件民族乐器，常见讨论会涉及 ZUNpet（Romantic Tp）、FM/芯片音色、铜管和密集的旋律编排。社区的 `THFont`/`NeoTHFont` 等包可以作为试听参考，但当前不自动下载：官方指南要求标明二次创作属性，并禁止公开原作游戏素材；旧的 ZUN 使用条件也要求内部数据不得再分发或修改。[官方指南](https://touhou-project.news/guideline/) 和 [历史条件转录](https://thbwiki.cc/二次创作以及使用规则/乐曲二次使用条件) 均不能替代音色包本身的第三方授权。

因此项目采用两条路线：默认使用 CC0/MIT/原创素材制作“ZUN 风格特征”音色，不复制原作样本；用户若自行取得社区音色，只能作为本地外部导入，并在发布前完成逐文件授权和哈希审查。

待自行核验的社区候选已整理在 [`assets/packs/EXTERNAL_CANDIDATES.md`](assets/packs/EXTERNAL_CANDIDATES.md)，其中包含 THFont、NeoTHFont、ZUNpet/ Romantic Tp 复刻包和相关资料索引，以及逐项核验表。该文档中的链接是研究入口，不表示项目已取得这些包的再分发权。

## 目录

```text
src/siegfridi/
  app/            # PySide6 窗口和交互
  core/           # 工程模型、tick/PPQ、命令栈和 .siegfridi 序列化
  midi/           # Mido/RtMidi 适配
  audio/          # PyAV/FFmpeg 和预处理
  transcription/  # Basic Pitch、节拍和结果映射
  playback/       # FluidSynth 和 MIDI 时钟
  sound/          # SoundProfile、风格模板、音色包清单
  workers/        # 可取消的工作进程入口
packaging/        # PyInstaller spec、原生 DLL hook 和第三方声明
tests/
assets/packs/     # 已授权或自制的音色包（大文件不入库）
assets/presets/   # 风格模板和示例工程
```

远端仓库：<https://github.com/SgfKrc/Siegfiridi>

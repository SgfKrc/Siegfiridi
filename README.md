# Siegfridi

Siegfridi 是一个 Python-first 的 Windows MIDI 编曲工具，优先服务定制化音轨生产，而不是先做通用 DAW 或完整 GM 音源。

一期的音乐方向以东方 Project 风格参考、以《恶魔城》《神之亵渎》为坐标的黑暗哥特风，以及 RPG Maker / BLACK SOULS I-II 语境下的复古 RPG 音轨为审美坐标。参考作品只用于描述风格特征，不复制其旋律、采样、工程文件或其他受保护素材。项目专用音色包、`SoundProfile` 和风格模板与 MIDI 工程分离，方便在不改音符的情况下切换配器。

## 当前状态

P3 音频转录管线已可实际运行：环境固定为 `numpy<2`、TensorFlow 2.14、Basic Pitch 0.4，并已用合成三音符 WAV 实测生成 3 个候选音符。P4 已接入 SoundFont 清单/哈希校验、FluidSynth CLI 渲染和 pyFluidSynth 原生绑定兜底；当前环境已用 `TimGM6mb.sf2` 实测生成有声 WAV。

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

音频、转录和合成依赖按需安装：`.[audio]`、`.[transcription]`、`.[synthesis]`。发布版会通过 PyInstaller 生成 Windows 安装包，并附第三方许可证、模型和音色包来源清单。

## 目录

```text
src/siegfridi/
  app/            # PySide6 窗口和交互
  core/           # 工程模型、tick/PPQ、命令栈
  midi/           # Mido/RtMidi 适配
  audio/          # PyAV/FFmpeg 和预处理
  transcription/  # Basic Pitch、节拍和结果映射
  playback/       # FluidSynth 和 MIDI 时钟
  sound/          # SoundProfile、风格模板、音色包清单
  workers/        # 可取消的工作进程入口
tests/
assets/packs/     # 已授权或自制的音色包（大文件不入库）
assets/presets/   # 风格模板和示例工程
```

远端仓库：<https://github.com/SgfKrc/Siegfiridi>

# N6 发布交接包

N6 的本机可完成部分已经固化为 Windows onedir 交付流程。构建产物位于
`dist/`，默认包括：

- `Siegfridi-0.1.0-win64.zip`：可复制到无 Python 的 Windows 10/11 x64 机器。
- `Siegfridi-release.json`：版本、目录名、ZIP 文件名和 ZIP SHA-256。
- `Siegfridi-release.sha256`：可直接用 `Get-FileHash` 对照的校验行。
- `Siegfridi-package-report.json`：目录内文件数量和必需资源校验结果。
- `Siegfridi/`：未压缩 onedir，便于定位启动或 DLL 问题。

## 构建

在已经安装 `.[all]` 且能访问 FluidSynth DLL 的 Windows 构建机执行：

```powershell
.\scripts\build.ps1 -Clean
```

如果 PyInstaller 已完成但压缩阶段被中断，可只重做归档：

```powershell
.\scripts\finish-release.ps1
```

脚本会生成原创 CC0 东方 Project / 黑暗哥特 SF2，运行 PyInstaller，收集
Qt、Basic Pitch、TensorFlow、FFmpeg/PyAV 和 FluidSynth 运行时，写入固定依赖
快照、三个原始示例工程、第三方声明和 `package-manifest.json`，然后执行：

1. `Siegfridi.exe --version` 版本冒烟；
2. offscreen UI 运行 10 秒冒烟；
3. 必需文件、文件大小、SHA-256 和禁止资产检查；
4. ZIP 压缩及归档 SHA-256 生成。

## 干净机验收

1. 将 ZIP 和 `Siegfridi-release.sha256` 复制到 Windows 10/11 x64 干净机。
2. 用 `Get-FileHash .\Siegfridi-0.1.0-win64.zip -Algorithm SHA256` 对照交接文件。
3. 解压后无需安装 Python，先运行 `Siegfridi.exe --version`，再双击启动。
4. 按 [`VISUAL_CHECKLIST.md`](VISUAL_CHECKLIST.md) 检查三套主题、背景图透明度、
   钢琴键盘、时间标尺、播放游标和高 DPI 布局。
5. 依次打开解压目录的 `_internal/assets/presets/` 下的三个 `.siegfridi` 示例，执行编辑、保存、
   播放和 WAV 渲染；有音频文件时再验证 Basic Pitch 转录和取消。
6. 在有 MIDI 键盘的机器上验证端口刷新、缺件映射、note-on/note-off、力度和
   断开恢复。真实声卡、驱动和热插拔仍属于本步骤的机器验收范围。

## 已知限制

- onedir 约 1.5 GB，主要来自 TensorFlow/Basic Pitch 模型；首次解压需要足够磁盘空间。
- 构建时可能报告可选 `tbb12.dll`、CoreML 或 tflite 后端缺失；Windows CPU 转录路径
  已随包提供，构建脚本会把非零退出视为失败。
- offscreen 冒烟不能替代真实字体、高 DPI、声卡和 MIDI 驱动验收；这些项目已列入
  `VISUAL_CHECKLIST.md` 和本交接步骤。

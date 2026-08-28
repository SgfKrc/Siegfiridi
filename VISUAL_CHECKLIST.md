# Siegfridi 视觉验收清单

N7-005 的基准图由 `scripts/check-gui-visual.py` 生成。脚本不修改工程文件或 QSettings，只在 `.siegfridi/visual/` 写入 PNG 和 `report.json`。

## 自动检查

在仓库根目录、已激活 `.venv` 中运行：

```powershell
python scripts/check-gui-visual.py --output-dir .siegfridi/visual/n7-005
python scripts/check-gui-visual.py --output-dir .siegfridi/visual/n7-005-hidpi --scale-factor 1.25
```

基准矩阵：

| 文件 | 主题 | 请求尺寸 | 检查内容 |
| --- | --- | --- | --- |
| `dark-gothic-desktop.png` | Dark Gothic | 1440×900 | 深色对比度、钢琴键盘、控制区滚动 |
| `quiet-light-desktop.png` | Quiet Light | 1440×900 | 浅色对比度、输入控件边界 |
| `high-contrast-narrow.png` | High Contrast | 900×700 | 窄屏滚动、钢琴卷帘可见区、无音频状态 |

`report.json` 必须显示请求尺寸与实际逻辑尺寸一致、DPR 正常、截图非空、控制区和卷帘都在工作区内，并且 `status` 包含 `no MIDI output device`。

## Windows 实机人工检查

- 在 100%、125%、150% 和 200% 显示缩放下打开窗口，确认标题、组框、按钮、输入框和状态栏文字完整显示。
- 分别切换 Dark Gothic、Quiet Light、High Contrast，确认文字、网格、钢琴键盘和粉色音符之间有足够对比度。
- 在 900×700 窗口滚动左侧控制区，确认右侧钢琴卷帘不随面板滚动消失，且没有水平滚动条或控件互相覆盖。
- 没有 MIDI 输出设备时点击 Play，确认状态栏显示无设备回退，不弹出阻塞式错误窗口，Stop 仍可恢复界面。
- 选择明亮背景图并调整透明度/保护强度，确认音符、键盘、轨道列表和状态栏仍可读。
- 在真实声卡、MIDI 设备和字体环境下重复一次打开/保存、播放、导入取消和转录失败路径。

当前 offscreen CI 环境 `QFontDatabase.families()` 为空，因此自动截图只作为布局、几何、色彩和非空检查；文字字形、高 DPI 字体栅格化和真实硬件项目不能由该环境替代。

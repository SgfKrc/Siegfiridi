# Test Quality Audit

审计日期：2026-08-29

## 当前基线

- `pytest --collect-only -q`：135 项收集项。
- `coverage run --branch -m pytest -q && coverage report -m`：全量通过，源码分支覆盖率 88%，`fail_under` 仍为 80%。
- 关键模块覆盖率：`app/piano_roll.py` 92%、`core/models.py` 100%、`midi/files.py` 92%、`workers/transcription.py` 93%、`sound/profiles.py` 100%。
- `ruff check src tests scripts`：通过。
- `scripts/check-gui-visual.py`：dark-gothic、quiet-light、high-contrast 窗口场景均通过，截图与工作区几何检查正常。

## 本次审计与更新

- 将 coverage 配置明确设为 `branch = true`，以后审计同时关注语句和条件分支。
- 补充 `Note`、`Track`、`Project`、`SoundProfile`、`StylePreset` 的非法边界输入测试，避免无效 MIDI 值和混音参数进入核心模型。
- 补充分组编辑命令的身份语义、空 undo/redo、监听通知和 MIDI 同音并发 FIFO 配对测试。
- 补充 MIDI velocity-zero note-off、尾部缺失 note-off 和导出同刻 note-off 优先级回归测试。
- 补充 Basic Pitch 导入失败、推理失败、模型缺失、预测结构归一化测试，不依赖真实模型即可验证依赖冲突降级行为。
- 补充转录 worker 的成功消息、空轮询、重复启动、取消活进程和上下文管理器测试。
- 补充选择模式快捷键、音域夹紧、半透明预览、Esc 清理剪贴板和空轨道反馈测试。
- 审计期间修复一个真实缺陷：MIDI 导入器在轨道省略尾部 `note_off` 时错误采用已闭合音符的结束点，导致尾音被截断；现在使用实际轨道结束 tick 作为安全边界。

## 验证记录

```text
135 passed
TOTAL branch coverage: 88%
ruff check: All checks passed
GUI visual: 3 scenarios passed
git diff --check: passed (仅有 Git 的 LF/CRLF 提示)
```

Basic Pitch 实机测试仍可能输出 TensorFlow、`pkg_resources` 和 Python 3.13 弃用警告；这些来自可选依赖，不影响本次测试结果。

## 残余风险

- Qt 测试使用 `offscreen` 平台，不能替代 Windows 实机的字体、高 DPI、窗口管理器和真实鼠标拖拽验收。
- MIDI 端口使用模拟对象，不能替代真实声卡、热插拔和不同 RtMidi 后端测试。
- Basic Pitch、FluidSynth 和音色包的资产测试在依赖或本地资产缺失时跳过；无外部资产的错误路径已有覆盖。
- 真实冻结包仍需按 `N6_RELEASE_HANDOFF.md` 在干净机执行启动、播放、MIDI 和视觉清单。

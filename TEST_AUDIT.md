# Test Quality Audit

审计日期：2026-08-28

## 基线

- 审计前 `pytest --collect-only`：90 个收集项，78 个测试函数。
- 首轮源码语句覆盖率：86%。审计时发现 coverage 默认把 Qt/启动辅助文件也记入数据，已在 `pyproject.toml` 限定 `src/siegfridi`，并设置 `fail_under = 80`。
- 主要缺口：`main_window.py` 的设备交互分支、`core/project_io.py` 的损坏/恢复路径、`midi/input.py` 的端口生命周期，以及播放设备发现异常。

## 本次更新

- 增加 MIDI 映射边界、velocity-zero note-off、非音符消息、回调绑定失败和关闭竞态测试。
- 增加播放输出枚举和打开失败测试，覆盖后端返回 `ValueError` 的情况。
- 增加项目文件缺字段、嵌套数据损坏、非法 JSON、后缀校验和原子写失败恢复测试。
- 增加 Qt 场景级 MIDI 连接、映射刷新、MIDI Thru、断开释放悬挂音符、输出失败，以及背景文件/透明度边界测试。

审计后 `pytest --collect-only` 为 107 个收集项；全量 `coverage run -m pytest -q && coverage report -m` 结果为源码语句覆盖率 89%，其中 `main_window.py` 87%、`project_io.py` 92%、`midi/input.py` 96%、播放设备模块 92%。CLI 入口的参数解析和 launcher 委托已覆盖，模块保护式启动行仍只在真实命令启动时执行。

## 残余风险

测试仍使用 Qt offscreen 和模拟 MIDI 端口，不能替代真实声卡、真实 MIDI 热插拔和不同 RtMidi 后端的验收；这些保留在干净机验收清单中。可选 Basic Pitch/FluidSynth 资产测试在依赖或音色包缺失时跳过，核心错误路径仍由无外部资产的单元测试覆盖。

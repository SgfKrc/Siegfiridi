# 音色包目录

运行时音色包目录仅放入自制或已获授权的 `.sf2`/`.sf3` 音色包。每个音色包都应有同名的来源、许可证、哈希和映射说明；大型音频资产默认不提交 Git。制作阶段的 SFZ/WAV 源素材统一放在 `sources/`，不得被当作可直接加载的运行时包。清单中的 `distribution` 必须为 `redistributable` 才能进入发行包；`local-study-only` 仅允许本地试听。

当前已获取 `FluidR3_GM.sf2` 3.1 作为 GM 回退基线，配套清单为 `fluidr3-gm.json`，许可证文本为 `FluidR3_GM.COPYING`。可用 `scripts/fetch-soundfont.ps1` 按固定地址和 SHA-256 重新获取。该包不是东方 Project / 黑暗哥特专用音色；专用包仍需原创采样或逐项取得授权。

已另行获取 [SP Bamboo Flute](https://github.com/NeoSoundFonts/SP-Bamboo-Flute) 的 CC0-1.0 源素材（固定提交版本见 `sp-bamboo-flute-source.json`）。该资源是 SFZ/WAV，当前 FluidSynth 渲染链不能直接加载；原始素材位于 `sources/sp-bamboo-flute/`，由 `.gitignore` 排除大文件，可用 `scripts/fetch-oriental-source.ps1` 按归档 SHA-256 重建。它只作为东方风格的竹笛/装饰音源候选，不等同于项目专用音色包；转换为 SF2、映射和听感验收仍是后续工作。

已获取 [FreePats Ocarina](https://freepats.zenvoid.org/Wind/ocarina.html) 的 CC0-1.0 SF2（2024-10-02），清单为 `freepats-ocarina.json`，许可证和录音说明分别为 `FreePats-Ocarina.CC0.txt`、`FreePats-Ocarina.SOURCE.txt`。可用 `scripts/fetch-freepats-ocarina.ps1`（需 `.[assets]` 的 `py7zr`）重新获取和校验；该包可作为东方风格的可运行风笛候选，但仍不是完整项目专用包。

已生成 `oriental-project-v0.1.sf2` 作为项目第一版原创东方风格音色包，清单为 `oriental-project-v01.json`，许可证和来源说明分别为 `OrientalProjectPalette.CC0.txt`、`OrientalProjectPalette.SOURCE.txt`。它由 `scripts/build-oriental-pack.py` 确定性生成，包含原创铜管攻击、FM/芯片主音、呼吸风笛和芯片打击乐程序，不含 Touhou、ZUNpet、Roland、游戏或第三方录音；可直接用于 FluidSynth 和项目模板试听。

已生成 `dark-gothic-v0.1.sf2` 作为项目第一版原创黑暗哥特风格音色包，清单为 `dark-gothic-v01.json`，许可证和来源说明分别为 `DarkGothicPalette.CC0.txt`、`DarkGothicPalette.SOURCE.txt`。它由 `scripts/build-gothic-pack.py` 确定性生成，包含教堂管风琴、暗黑合唱、葬礼钟、低音弦乐、拨弦遗物和哥特打击乐程序，不含《恶魔城》《神之亵渎》、BLACK SOULS、游戏或第三方录音；可直接用于 FluidSynth 和 `dark-gothic` 模板试听。

社区常见的 `THFont`、`NeoTHFont`、`ZUNpet` 等包只作为外部参考，不随项目获取或分发。其标签或第三方页面的许可证声明不能证明其中的 Roland/游戏内部样本具有再分发权；东方官方指南还禁止公开原作游戏素材。用户可以在本地自行取得并通过导入清单使用，但发布项目时必须提供来源、原始授权、允许修改/再分发范围和 SHA-256，否则保持排除。

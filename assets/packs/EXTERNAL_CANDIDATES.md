# 外部音色包自核验清单

本文件列出可用于试听、研究或本地导入的候选资源。它们不代表项目已取得再分发授权；未通过“来源、原始授权、格式、哈希”四项核验前，不得复制到仓库或发行包。

## 核验规则

1. 记录资源页面、直接下载地址、作者、版本/发布日期和下载日期。
2. 保存许可全文或稳定的许可链接，确认是否允许修改、商业/非商业使用和再分发。
3. 对原始归档和解包后的每个运行时文件计算 SHA-256；转换为 SF2/SF3 后重新计算。
4. 检查是否包含 Roland、游戏 ROM/安装包或其他第三方内部样本。页面标注 `WTFPL`、`public domain` 或“免费”不能代替样本来源证明。
5. 社区包只允许作为本地外部导入；默认发行包使用项目原创或 CC0/MIT 等来源清晰的资产。
6. 本项目明确“复刻风格、不得其形”：使用社区东方音色包时，发行说明必须注明二次创作、保留作者署名，并按各包许可声明禁止商业使用（或注明适用范围）。

## 候选记录

> 调研日期：2026-08-28。Musical Artifacts 实时页面会对脚本访问返回 Cloudflare 403，下列条目均经 archive.org Wayback Machine 存档核实；GitHub 条目经 REST API 与 README 核实；MediaFire 外链为实时直访。未核实项已逐条标注。

| 候选 | 入口 | 作者/上传者 | 许可声明 | 当前判断 | 需核对的关键项 | 建议 |
| --- | --- | --- | --- | --- | --- | --- |
| THFont / Touhou Soundfont #433 | [MA #433](https://musical-artifacts.com/artifacts/433)（249 MB `Touhou.sf2`） | Team Shanghai Alice (game)、SF 作者匿名 | **CC BY 4.0**（可署名再分发） | 社区标准东方参考包，2016-11-23 上传、近年持续更新，约 25.5 万次下载；含 Romantic Tp 与 SD90 鼓组，其中 Romantic Tp 真伪有社区争议 | 原始提取出处未标注（未核实）；Romantic Tp/SD90 样本来源 | 首选参考包；按 CC BY 署名可随包再分发，须下载后重算哈希并保存许可全文 |
| NeoTHFont #6614 | [MA #6614](https://musical-artifacts.com/artifacts/6614)（281.77 MB，MediaFire 外链） | 匿名，2025-07-20 | **WTFPL 2.0**（可自由再分发） | 标注 sc-88 pro/zun/touhou/sf2，社区视为 THFont 重制改进版；MediaFire 链接已实测在线 | 具体样本构成（页面未详述）；axfc 镜像可访问性 | 候选；须下载否核哈希与归档内 NOTICE/README |
| ZUNpet 真·SD-90 Romantic Tp #2527 | [MA #2527](https://musical-artifacts.com/artifacts/2527)（74.4 MB，单音色） | “roland blah blah”，2022-12-07 | **WTFPL 2.0**（可自由再分发） | 上传者宣称是非 THFont 版的真实 ZUNpet（SD-90 Romantic Tp） | ⚠️ 若确为 Roland 硬件采样，Roland 权利仍可能覆盖；原始提取出处未标注 | 仅本地导入试听；不建议随包再分发 |
| UltimateSoundfontModForTouhou | [GitHub 仓库](https://github.com/GdGohan/UltimateSoundfontModForTouhou) | GdGohan（Mod）；内含 ZUN 游戏原声 | **无 LICENSE**（默认保留所有权利） | 整合外链音源+游戏 AAC 原声的 mod 包；无 Releases 资产 | 内含游戏原声，东方官方指南禁止公开原作游戏素材 | 仅作资料索引，不可再分发 |
| Roland SC-88 (Full Version) #538 | [MA #538](https://musical-artifacts.com/artifacts/538)（21.8 MB） | Mr.Sanic，2017-11-26 | WTFPL 2.0 + 附加条款“不得冒名再分发” | 从付费 Roland Sound Canvas VST 试用版截取编译 → 许可存疑 | Roland 商业软件试用版采样权利 | 排除；不进入项目 |
| FreePats Ocarina 2024-10-02 | [FreePats 页面](https://freepats.zenvoid.org/Wind/ocarina.html) | FreePats 社区 | **CC0-1.0** | 已下载并实测 FluidSynth 渲染；清单/哈希/CC0 文本齐备 | 保留录音者署名、归档和 SF2 哈希 | 已纳入本地候选清单 |
| SP Bamboo Flute | [GitHub 仓库](https://github.com/NeoSoundFonts/SP-Bamboo-Flute) | NeoSoundFonts | **CC0-1.0** | 已固定提交并逐文件记录哈希；SFZ/WAV 源素材 | 转换后的 SF2 映射、循环、力度和新哈希 | 已获取为制作源，尚不能直接渲染 |

## 已搜集的社区东方音色包（2026-08-28 调研）

### 可自由再分发（许可清晰，可本地导入并考虑随包署名分发）

| 条目 | 作者/时间 | 许可 | 下载 | 说明 |
| --- | --- | --- | --- | --- |
| Touhou Soundfont #433 | SF 作者匿名 / 2016-11-23 | CC BY 4.0 | MA 站内 `Touhou.sf2` | 东方风格首选：GM 全兼容 + 附加 bank |
| PC-98 Soundfont #589 | kakuzatoo / 2018-07-20 | CC BY 4.0 | MA 站内（29.2 MB） | PC-98（YM2608）时代东方 TH01–05 风味参考 |
| Touhou Roland SRX EoSD Romantic Trumpet #1783 | Palto, DrKoupop / 2021-10-16 | WTFPL 2.0 | MA 站内（116 MB） | 红魔乡标志性小号单乐器参考 |
| Actually the zunpet #2527 | “roland blah blah” / 2022-12-07 | WTFPL 2.0 | MA 站内（74.4 MB） | ZUNpet 单音色，Roland 采样疑点见上表 |
| NeoTHFont #6614 | 匿名 / 2025-07-20 | WTFPL 2.0 | [MediaFire（已实测在线）](https://www.mediafire.com/file/jx88lp0akwb0nep/NeoTHFont.tar.xz/file) + [axfc 镜像](https://www.axfc.net/u/4101992) | 281.77 MB，THFont 重制版 |
| Altosoft Vib #1360 | — | CC BY 3.0 | MA 站内 | zun 标签下的可再分发条目 |

### 仅个人使用 / 不可再分发（Roland、Edirol 或游戏数据灰区，只能本地试听）

| 条目 | 作者/时间 | 页面许可 | 下载 | 风险 |
| --- | --- | --- | --- | --- |
| Touhou Soundfont Collection #1327 | 未知 / 2020-10-19 | Non-free | MA（392 MB zip，THFont/THDrum/THInst 合集） | 无已知许可 |
| Edirol SD-90 Pack I (Complete) #1367 | rosntdoxot 等 / 2020-11-15 | Non-free（“All rights reserved to Roland”） | MA（5.46 GB rar） | Roland SD-90 采样，ZUN 标志性音源最重要来源 |
| The Grand 3 Yamaha C7 Player #2026 | 未知 / 2022-04-05 | Non-free | MA（41.6 MB） | ZUN 近年钢琴采样版 |
| Edirol SD-90 Drum Kits #1440 / Pack II #1539 | — | Gray Area | MA / Google Drive | Roland 采样版权灰区 |
| SD-90 Intim8String #2031 | — | 注明“可公开分享、禁止出售” | MA | 禁止出售 |

### 说明

- MusicaArtifacts `touhou` 标签共 47 个条目（sf2 40 个）、`zun` 标签 33 个；上表为按许可清晰度筛选的代表性条目。
- GitHub 上不存在公认的、带开放许可的东方风格 SF2 音色包仓库；相关仓库（GdGohan/UltimateSoundfontModForTouhou、AyHa1810/touhou-midi-collection 等）均无 LICENSE 或非音色包，仅作参考。
- ZUNpet 官网（zunpet.fc2web.com）已于 2025-06-30 终止服务且无 Wayback 存档，原始“个人使用限定”条款无法逐字核实；现存途径即 MA #2527。
- 配套 MIDI 生态：GameBanana “Touhou Midis”（projects/35179）、AyHa1810/touhou-midi-collection（无 LICENSE，仅浏览）。

## 东方官方边界

东方官方指南要求明确说明是东方二次创作，并禁止公开原作游戏素材、误导为官方或侵犯他人权利；旧的 ZUN 使用条件转录还要求内部数据不得再分发或修改。非商业只解决商业性这一项，不能自动授予原作内部音频或第三方音色包的再分发权。

- [东方 Project 二次创作指南（官方，2024-05-31）](https://touhou-project.news/guideline/)
- [ZUN 历史使用条件转录（THBWiki）](https://thbwiki.cc/二次创作以及使用规则/乐曲二次使用条件)

## 项目决策

方向是“ZUN 风格特征重构”，而非复制“ZUN 音源”（复刻风格、不得其形）：优先使用 CC0/原创铜管、FM/芯片、打击乐和效果样本，结合密集旋律、短动机、力度和音符时值塑造听感。

社区东方音色包的使用规则（2026-08-28 明确）：

1. **可使用**许可清晰的社区东方音色包（CC BY 4.0 / WTFPL / CC0 等），如 MA #433、#589、#1783、#2527、#6614、#1360；每个包保留许可全文、作者署名与最新 SHA-256。
2. **必须注明**：发行说明与包内 NOTICE/CREDITS 明确标注为“东方 Project 二次创作参考音色”，与原作无关；按各包许可条款声明禁止商业使用（或注明允许范围）。
3. **保持在本地**：Roland/Edirol/游戏数据灰区包（#1327、#1367、#2026、#1440、#1539、#2031 等）只允许用户自行核验后本地通过 `SoundPackManifest` 导入，不随项目发行包分发。
4. 只有完成本表核验并补齐许可证文件后，才可进入发布构建。
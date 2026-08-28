# 外部音色包自核验清单

本文件列出可用于试听、研究或本地导入的候选资源。它们不代表项目已取得再分发授权；未通过“来源、原始授权、格式、哈希”四项核验前，不得复制到仓库或发行包。

## 核验规则

1. 记录资源页面、直接下载地址、作者、版本/发布日期和下载日期。
2. 保存许可全文或稳定的许可链接，确认是否允许修改、商业/非商业使用和再分发。
3. 对原始归档和解包后的每个运行时文件计算 SHA-256；转换为 SF2/SF3 后重新计算。
4. 检查是否包含 Roland、游戏 ROM/安装包或其他第三方内部样本。页面标注 `WTFPL`、`public domain` 或“免费”不能代替样本来源证明。
5. 社区包只允许作为本地外部导入；默认发行包使用项目原创或 CC0/MIT 等来源清晰的资产。

## 候选记录

| 候选 | 入口 | 当前判断 | 需核对的关键项 | 建议 |
| --- | --- | --- | --- | --- |
| THFont / Touhou Soundfont | [Musical Artifacts 搜索](https://www.musical-artifacts.com/artifacts?formats=sf2&tags=sc-88+pro%2Csc-88pro) | 社区常用东方复刻参考；页面可能聚合多个上传者和不同文件 | 每个具体条目的原作者、样本来源、许可证全文、是否含游戏/硬件内部数据 | 仅试听和本地导入，不自动下载 |
| NeoTHFont | [Musical Artifacts 条目搜索](https://www.musical-artifacts.com/artifacts?formats=sf2&tags=sc-88+pro%2Csc-88pro) | 有 `Touhou`、`zun`、`sc-88` 等标签，但标签不等于完整授权链 | 下载归档内的 NOTICE/README、样本来源、再分发条件、版本哈希 | 未完成授权核验前排除 |
| ZUNpet / Romantic Tp 复刻 | [ZUNpet 资料](https://scrapbox.io/0b5vr/ZUN%E3%83%9A%E3%83%83%E3%83%88) | “ZUNpet”通常指 Roland EDIROL SD-90 的 Romantic Tp；原硬件音色不是开放音源 | Roland 音色版权、具体复刻包的作者许可、是否只是预设参数还是采样数据 | 用 CC0/原创铜管或 FM 合成重构，不复制 SD-90 样本 |
| UltimateSoundfontModForTouhou | [GitHub 仓库](https://github.com/GdGohan/UltimateSoundfontModForTouhou) | 仓库列出 Touhou Soundfont、Zunpet、SC-55 等外链，但未提供统一资产许可证 | 每个外链包分别核对来源、许可证、原始文件哈希和再分发范围 | 作为资料索引，不作为项目依赖 |
| FreePats Ocarina 2024-10-02 | [FreePats 页面](https://freepats.zenvoid.org/Wind/ocarina.html) | CC0-1.0，SF2，已下载并实测 FluidSynth 渲染 | 保留录音者署名、CC0 文本、归档和 SF2 哈希 | 已纳入本地候选清单 |
| SP Bamboo Flute | [GitHub 仓库](https://github.com/NeoSoundFonts/SP-Bamboo-Flute) | CC0-1.0，SFZ/WAV，已固定提交并逐文件记录哈希 | 转换后的 SF2 映射、循环、力度和新哈希 | 已获取为制作源，尚不能直接渲染 |

## 东方官方边界

东方官方指南要求明确说明是东方二次创作，并禁止公开原作游戏素材、误导为官方或侵犯他人权利；旧的 ZUN 使用条件转录还要求内部数据不得再分发或修改。非商业只解决商业性这一项，不能自动授予原作内部音频或第三方音色包的再分发权。

- [东方 Project 二次创作指南（官方，2024-05-31）](https://touhou-project.news/guideline/)
- [ZUN 历史使用条件转录（THBWiki）](https://thbwiki.cc/二次创作以及使用规则/乐曲二次使用条件)

## 项目决策

当前默认路线是“ZUN 风格特征重构”，而非复制“ZUN 音源”：使用 CC0/原创铜管、FM/芯片、打击乐和效果样本，结合密集旋律、短动机、力度和音符时值塑造听感。用户自行取得的 THFont/NeoTHFont/ZUNpet 包可以在本地通过 `SoundPackManifest` 导入；只有完成本表核验并补齐许可证文件后，才可进入发布构建。

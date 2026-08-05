# 项目级 Research

本目录保存围绕一个明确问题开展的有界研究。Research 可以得到正面、负面或边界结论，也可以尚处于孵化阶段；它不因文件很多、实验很多或已经完成，就自动成为一篇论文。

`Study/` 与本目录的区别是：Study 必须具有足以形成独立小论文的中心问题、方法、证据、解释、贡献和边界；Research 只需要把一个问题研究清楚，并准确说明它与现有 Study 的关系。

## 状态模型

每项 Research 同时记录两条彼此独立的状态：

- **成熟度**：`COMPLETE`、`ACTIVE`、`NEEDS_REVIEW`、`INCUBATING`；
- **关系角色**：`INDEPENDENT`、`SUPPORTING`、`EMBEDDED`、`SUPERSEDED`、`HISTORICAL`。

“完成”描述研究问题是否已有可复核答案；“支撑、嵌入、被取代或历史”描述它与当前 Study 和现行证据的关系。归档不等于无用，完成也不等于可以写入任意论文。

## 当前研究地图

| Research | 核心问题 | 成熟度 | 关系角色 | 当前用途 |
|---|---|---|---|---|
| `01-参数估计评价指标/` | 三参数 Weibull 估计结果应从哪些互不混淆的视角评价 | `NEEDS_REVIEW` | `SUPPORTING` | 保存早期指标研究，并索引 Study01 当前 J1 决策；旧文献统计不冒充系统综述 |
| `02-MDM根存在条件与稳健求解/` | MDM 偏移方程何时有根、无解来自哪里、怎样稳健求解 | `COMPLETE` | `SUPPORTING` | 支撑当前 MDM 实现，并保留理论与数值来源 |
| `03-NN输入表征与样本量机制/` | 在 Study01 风险曲线任务中，F13/F12/RAW 与跨样本量训练有什么差异 | `COMPLETE` | `SUPPORTING` | 原 Study015；解释 Study01 输入和训练组织的适用边界，不进入其 formal 证据链 |
| `04-直接NN参数估计/` | NN 直接参数估计路线在不同输入、学习范式和对照下表现如何 | `NEEDS_REVIEW` | `SUPPORTING` | 索引 Study01 P3/P4、Study02 前置 A，并保存旧 E09 历史探索；不同协议不得拼接排名 |
| `05-传统估计方法横向比较/` | 固定条件下不同传统估计方法的误差和失败行为如何 | `NEEDS_REVIEW` | `INDEPENDENT` | 有运行产物，但存在尺度等价、失败惩罚、基线测试和历史换行 seal 缺陷，复核前不可升级结论 |
| `06-MDM估计量特性与截尾扩展/` | MDM 估计量的偏差规律、截尾行为和区间性质如何 | `NEEDS_REVIEW` | `INDEPENDENT` | 有压缩包内代码和结果，尚缺顶层 manifest、哈希和独立审计 |
| `07-等变残差修正/` | 能否在保留经典骨架的同时学习有限样本修正并避免渐近损害 | `INCUBATING` | `INDEPENDENT` | 已有方向批判和文献材料，尚无冻结协议或实验 |
| `08-截尾分位寿命修正/` | 截尾小样本中能否以学习型修正改善目标分位寿命 | `INCUBATING` | `INDEPENDENT` | 目前只有研究设想，不是已完成项目 |

## 嵌入式支撑研究

以下研究在科学身份上属于 Research，但因代码、formal artifacts、manifest 和历史 SHA 与所属 Study 深度绑定，保持原位：

- **Study02 前置研究 A：NN 参数估计基础**
  - 入口：`../Study/02-study-NN参数估计与分位点目标研究/06-A-前置研究报告.md`
  - 状态：`COMPLETE + EMBEDDED`。它是 Study02 参数路线的冻结依据，不是 Study02 的独立论文贡献。
- **Study01 Direct-MLP/P3/P4 对照**
  - 代码与封存产物保持在 Study01 原路径，由 `04-直接NN参数估计/README.md` 统一说明。它不参与 Study01 当前论文主论证。

## 归档

`archive/` 保存被后续 Study 取代的研究前史、题名与内容不一致的待澄清材料，以及旧协议下的完整历史包。历史原文、日志、manifest 和封存产物不为了目录美化而改写。

## 使用规则

1. 每项 Research 只有一个当前 README 入口；提示词、旧轮次和被取代稿进入 `history/` 或 `archive/`。
2. Research 结果不得自动进入 Study。若要用于论文主张，必须在对应 Study 的研究问题、协议和证据索引中建立明确映射。
3. 不跨协议拼接数值，不用历史探索替代当前正式证据。
4. 负面结果和失败研究保留；没有正式执行的设想必须标为 `INCUBATING`。
5. 不为 Research 复制 Study02 的重型控制面；只保留回答当前问题所需的最小科学护栏。
6. 迁移历史见 `RELOCATION.json`；旧路径只用于理解 Git 历史，不再作为当前入口。

## 已知历史证据缺陷

`05-传统估计方法横向比较/` 的既有 manifest 记录 7 个输出。当前 Git 中 run log 的字节哈希匹配，6 个 CSV 的 LF 字节哈希不匹配；仅在确定性 LF→CRLF 重建后与历史记录一致。本次整理保持当前 Git blobs 和原 manifest 原样，不重新封存，也不把它描述为当前 byte-level seal 自洽。若未来继续该研究，应另开版本、重新运行并生成新的 manifest。

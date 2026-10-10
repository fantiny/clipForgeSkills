# ClipForge Skills

独立仓库：`fantiny/clipForgeSkills`。当前为 **v0.1.0 开发预览版**：9 个技能及本地制作主流程已实现，已有六类真实素材内部审阅片；完整规划与业务质量验收尚未完成。原 `fantiny/clipforge` 保留不变，本仓库仍按固定提交复用其 vidmake 引擎，暂未实现引擎完全独立。

以实际视频完成观众目标为验收方向，以 Codex / Claude Code 为交互入口，按需读取子 Skill，本地完成素材处理和视频合成。首期交付为 **MP4 + SRT + 可复现剪辑方案**，附封面、来源和审核记录。范围止于成片交付。

[开发计划与验收状态](docs/DEVELOPMENT_PLAN.md) · [业务开发指导](docs/BUSINESS_CONTENT_GUIDE.md) · [CLI / 数据契约](docs/API.md) · [技术栈](docs/STACK.md) · [提示词与Harness深入研究](docs/HARNESS_RESEARCH.md) · [连续调优复盘](docs/REFERENCE_BENCHMARK.md#11-连续制作调优复盘2026-10-10)

## 制作与验收方向

**观众要理解什么 → 画面和声音怎样支撑 → 先验证不确定的关键短段 → 整片预览 → 定位问题并局部修订 → 审阅正式成片。** 简单查询/样式小改直接执行对应能力。工具成功、模型自评分或文件齐全都不能代替实际看片/听音频。

参考项目的具体机制与取舍见[源码研究](docs/HARNESS_RESEARCH.md)，统一落地对应关系见[开发总览](docs/DEVELOPMENT_PLAN.md)。当前能执行本地制作与H1取证、H2创作恢复；自动语义证明、问题修复机器门禁及真实收益评测仍未完成。

## 当前可用

- 9 个共享 Skills：总入口、参考片拆解、素材库、场景打标、文案分镜、音频、剪辑、审核、交付。
- 本地只读入库、哈希去重、可重建索引、授权/SKU/包装筛选、时间码标签、素材缺口查询。
- 运营表导入保留单元格、公式、嵌图和素材索引。导入资料保持待确认，不能自动充当产品事实；实际业务源文件与生成产物不随仓库上传。
- 参考片限量抽帧、局部密集源帧与带原声片段；按需加载近看、选片、审阅修复和恢复指引；六类场景配置可复用。coverage按标注区间而非整文件长度筛选，候选仍需实际看片。
- 结果目标、段落用途、画面/声音要求、锁定项与问题的版本化创作记录；按段落读上下文，检查工件变化，预算不足明确报错。
- 固定版本的原有 vidmake 合成引擎；跨镜字幕/音轨、本地系统配音、原声保留、预览/正式渲染、局部修改和缓存。
- 事实及活动校验、版本审核、幂等交付、文件哈希验证、使用记录和结构化日志。

本版语义打标由宿主或人工基于证据完成。EditPlan v2新增完整动作区间保护、重点文字/卡片/CTA及淡变、音轨淡入淡出、旁白时间窗音乐让位、双遍响度归一化和最终文件响度复测；[执行边界与字段](docs/API.md)。未自动运行 ASR/OCR/YOLO，也未实现向量检索、任意图形动画、变速/转场或原生编辑器导出。真实六场景成片质量和双宿主完整会话尚待验收。本地CLI不额外调用付费模型；宿主可按用户授权单独使用云配音并入库。云调用/用量、实际扣费和本地渲染分别记账；宿主Token未知，不能把渲染external_api=0当整片零成本。

## 初始化

需要 Python 3.13、uv、带 libx264 与 libass 的 FFmpeg/ffprobe。先克隆完整仓库，再执行以下步骤。原引擎仓库目前为私有，需要具有读取权限的 Git 身份（本机可先 `gh auth login` / `gh auth setup-git`），或用下述 `--source` 指定已有检出。

```sh
uv sync --frozen
uv run python tools/engine/bootstrap.py
uv run python tools/dev/install_skills.py --host both
uv run python tools/clipforge.py doctor
```

已有原仓库时，bootstrap 可加 `--source /path/to/clipforge-original`，从固定提交提取引擎，不改原仓库。引擎保存在 `.runtime/`；未随代码分发。技能入口依赖完整工具包目录，请勿单独拷走 SKILL.md。

上述命令同样用于Windows PowerShell。安装器在`.agents/skills/`和`.claude/skills/`创建受管理副本，无需符号链接权限，支持工具包与目标项目位于不同盘符；`--project <目标目录>`安装到其他项目。更新仓库后重跑安装器同步指引；检测到用户改动或其他技能时拒绝覆盖。安装清单记录工具包位置，移动工具包后需重新配置安装。打开目标项目的新Codex / Claude Code会话使用，双宿主完整会话验收仍独立进行。

Windows适配实现及验收边界见[ADR-009](docs/ADR/009-windows-native-runtime.md)和[技术栈](docs/STACK.md)。数据与缓存建议保存在本地；共享素材使用Windows自己的盘符/UNC路径，不能直接使用macOS的`/Volumes/...`路径。Windows配音使用系统已安装的System.Speech声音，缺中文声音时提供已有录音；不自动下载模型或调用付费服务。doctor检查ass/libx264，中文字体与听感仍需实际看片确认。

原生Windows Server CI已通过102项组件测试（另跳过1项macOS测试），含真实系统配音、字幕/音轨合成与素材路径处理；[验证记录](https://github.com/fantiny/clipForgeSkills/actions/runs/38012727443)。完整私有引擎的Windows集成仍因缺少仓库Secret而跳过，不能将组件通过视为Windows10/11桌面完整制作已验收。

## 放入素材并开始

素材目录由使用者指定，只读导入。真实开发验收素材已完成本地索引和去重；公司素材数量、清单与索引不公开。SKU、包装版本与具体发布渠道按作品简报确认。

项目内备用投放目录：

- `inputs/media/raw/`：自有或获授权的原始视频、音频，可继续按日期/批次分子目录。
- `inputs/media/references/`：用于学习拆解的参考片，与成片素材分开。

在宿主中输入：

> 使用 clipforge。只用 inputs/media/raw/本次批次 中的素材，制作一条15秒的示例品牌实物展示视频，突出开盒和盛盘过程，不含价格促销，先输出内部审阅版。

按批次提供或选择素材，再用提示词说明本次目的、主推品、价格和成片要求即可。Agent整理简报、检查动作与镜头、完成选片；只追问影响本次成片的必要缺失或实际冲突，不要求重复确认已给信息。当前批次选片范围由Skill指引约束，CLI尚无强制批次过滤；正式促销仍需提供契约要求的活动期限和适用范围等信息。

或按单项任务使用：

> 使用 clipforge-reference，拆解我放在 inputs/media/references 的视频。按时间码区分观察、解释和可复用结构；没有热度数据就只作为参考片。

> 使用 clipforge-edit，只修改这版字幕颜色，其他内容不变。生成新版本并报告哪些镜头复用了缓存。

CLI 入库与查询示例：

```sh
uv run python tools/clipforge.py ingest inputs/media/raw
uv run python tools/clipforge.py search --include-unconfirmed --limit 5
uv run python tools/clipforge.py profiles
# 将路径和时间替换为实际需检查的区间
uv run python tools/clipforge.py evidence path/to/video.mp4 --start 1 --end 2 --every-frame
uv run python tools/clipforge.py status
```

新素材的授权和包装默认未知。根据实际业务资料补齐 metadata 后，才能进入生产方案；结构示例见 [共享流程](skills/clipforge/references/workflow.md)。日期必须带时区。资料中的参考价格、工艺、功效不能自动确认为事实。

## 跨轮创作与恢复

复杂新片先由宿主按`schemas/creative-state.v1.json`整理创作记录，再用：

```sh
uv run python tools/clipforge.py creative-save path/to/creative.json
uv run python tools/clipforge.py creative-context CONTENT_ID --beat BEAT_ID
uv run python tools/clipforge.py creative-save path/to/creative.json --expected CREATIVE_REVISION
```

使用实际返回的ID。上下文保留全片锁定项和blocking问题，工件改变后明确提示复查；它不授予审核批准。该记录独立于剪辑计划，当前交付命令未自动关联其中问题，宿主仍需核对。

## 从方案到交付

宿主按 `schemas/edit-plan.v1.json` 或 `schemas/edit-plan.v2.json` 生成方案，先检查素材覆盖与事实，再执行（v1保持兼容，新增文字/混音/动作字段须选v2）：

```sh
uv run python tools/clipforge.py validate path/to/plan.json
uv run python tools/clipforge.py render path/to/plan.json --mode preview
uv run python tools/clipforge.py render path/to/plan.json --mode final
uv run python tools/clipforge.py review REVISION path/to/actual-review.json
uv run python tools/clipforge.py deliver REVISION
```

将 `REVISION` 替换为实际 render 返回值。审核记录只能反映实际完成的看画面、听音频和业务核对。未审、过期、被篡改或属于预览的版本不能正常交付。技术测试只能取得 `test_delivered`，不能充当生产成片。

默认数据保存在 `.clipforge/`；可用 `--data <目录>` 隔离项目。原片不改动，重建依赖真实源文件、计划、锁定工具链和当前事实记录；交付包包含素材哈希，未打包全部原片。库迁移时同步根目录映射与来源媒体。

## 开发验证

```sh
uv run python tools/dev/check.py
PIP_CACHE_DIR="$PWD/tmp/pip-cache" .venv/bin/pip-audit --local
uv run python tools/dev/smoke.py
uv run python tools/dev/evidence_demo.py
uv run python tools/dev/creative_demo.py
```

`smoke.py` 用本地色卡与系统中文配音生成 12 秒技术样片，输出 `tmp/technical-demo/result.json`，保持待审，不写假批准。系统缺少可用中文声音时明确报错，日常剪辑仍可使用录制音频。

`evidence_demo.py` 生成两帧白闪的技术样例：8张概览帧全部漏掉事件，局部逐帧保留两张白帧及源PTS，结果在 `tmp/evidence-demo/result.json`。这验证取证能力，真实动作/文字的理解仍需看片。

`creative_demo.py`使用已有技术样片验证实际CLI的选段恢复、跨段阻塞保留和方案变化失效，结果在`tmp/creative-demo/result.json`；缺少技术样片时调用smoke生成。字符数变化不是Token收益，不能视为视频质量提升。

检查脚本运行复杂度、文件长度、技能安装、测试和覆盖率门禁。2026-10-10本轮本地全量回归189项通过、1项Windows专用测试跳过，覆盖96.29%；9技能校验及两套安装内容一致性通过，远端结果单独记录。GitHub默认执行不依赖私有引擎的基础检查；只有配置 `CLIPFORGE_UPSTREAM_TOKEN` 仓库Secret后才执行完整引擎集成检查（对原仓库 Contents 只读即可），缺少时明确跳过，基础检查成功不等于全量通过。参见 [GitHub Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) 与 [checkout 私有多仓库](https://github.com/actions/checkout#checkout-multiple-repos-private)。未将本机登录凭据复制到Actions。原有 vidtag 模型链路尚未接入此 CLI，后续按计划验证后扩展。

## 真实素材六类内部审阅片（仅本地）

本地观看路径由具体制作任务提供；下述为脱敏验收概况。六条实拍片覆盖种草、信息科普、观察分享、促销版式、咨询服务、门店介绍，含 MP4、字幕与可复现计划。业务信息后补时用 `purpose: internal_review` / `channel: internal_review`：允许保留未知 SKU/包装，全程强制水印，禁止正式 deliver。不是将内部审阅片伪装为技术测试；契约见 docs/ADR/007-internal-review-videos.md，复现命令和未验项见批次 README。

新音乐批次入口由制作任务记录在本地（例如 `outputs/<batch>/index.html`），覆盖六场景（促销位采用无价格选购版）。已有明确计划可用 `uv run python tools/production/render_plan_directory.py outputs/review-new-music-scenes` 先全部校验，再逐条复用缓存并渲染；脚本只处理1–24个子目录中的plan.json，不生成配音或审核批准。云配音由宿主按用户授权单独制作并作为已有音频入库；目前speech命令仍是本地系统语音入口。

云声音、服务时间码和新音乐选择的可复用方法见[音频指引](skills/clipforge-audio/references/voice-and-music.md)。本批四条云配音、两条音乐字幕不是固定模板；促销缺活动信息时明确为无价格选购版。技术检查、抽帧观察和实际听审分开，尚未认定达到参考片质量。

本轮远端代码验证（192147e）：[Windows/Ubuntu CI](https://github.com/fantiny/clipForgeSkills/actions/runs/38031743185)组件分别148/147项通过，依赖审计通过；私有引擎集成仍因缺少Secret跳过。后续仅文档提交不扩展该验证范围。

公开范围：通用代码、Skill、Schema、测试、锁文件和脱敏文档。公司运营指导保存在本地`docs/private/`，素材、项目计划和服务响应仍保存在忽略目录；新检出无需这些资料即可运行技术测试。发布采用干净代码树与全新初始提交，不迁入旧分支、PR或提交历史，见[发布边界](docs/ADR/008-independent-skills-repository.md)。协作者请重新克隆，避免推回旧历史。

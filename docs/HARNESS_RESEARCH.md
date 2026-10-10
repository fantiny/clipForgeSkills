# 参考项目的提示词与 Agent Harness 深入分析

2026-10-09。目标是改善真实素材选用、事实表达、视听关系与修改收敛，而不是增加技能数量。当前研究基于固定提交的源码和提示词；没有运行这些项目的付费模型，也没有它们在示例品牌任务上的对照实验。因此下面区分**源码机制、预期作用、本项目落地、待测效果**。

取证命令：`.venv/bin/python tools/research/capture_harness_sources.py`。55份选定文件的提交、路径、SHA256和行数保存在`tmp/harness-research/manifest.json`；这不是55份文件全部逐行审计的声明。重点函数和提示词段落见各节固定链接。没有依赖README的功能列表推定行为。

## 1. 先修正当前判断

首轮60项测试证明了本地文件处理、部分契约和交付保护；不能证明选片相关、文案有说服力或审美质量。当前提示词多停留在“检查事实、选择素材、生成方案”的任务说明，缺少改变编辑决策的判据、失败示例和闭环。

实际复现：源视频6秒，某动作标签仅覆盖0–0.5秒，分镜需要2秒；原`coverage`返回missing=0。原因是按整文件时长检查，且先取Top5再筛时长。证据保存在`tmp/harness-research/coverage-probe/result.json`。这是“流程能跑”与“片段真能用”的具体差距。

本轮已修：先筛选同一匹配标注区间的长度再取Top5，返回usable_ranges；不同时间的标签不拼成一个动作。新增复现、后排有效候选、无关键词与异常时长测试。此修复仍不能证明标签语义真实，必须保留实际看片环节。

## 2. Hypit：把创作意图保留到执行与审阅中

源码：[语义与时间][h-script]、[参考片理解][h-reference]、[B-roll关系][h-broll]、[审阅及修复归属][h-review]、[Prompt Kits][h-kits]、[调度器][h-scheduler]。

### 提示词如何改变行为

- Script是目标语言的唯一权威，显示文字与读法是同一内容的不同投影；Segment按可表演的意思划分，而非按每个镜头切分。Selection和Moment让画面对应一段意思或一个事件。作用是减少改配音后字幕、画面继续沿用旧秒数的漂移。
- 参考分析在全貌与局部之间来回验证：先解释注意力和叙事的发展，再用连续帧、词时间、片段检查关键关系；不是一次抽几帧就结束。
- B-roll先决定与意思的关系：确切证据、跨多图的一段视觉解释、界面说明等；不是每个名词配一个镜头。来源播放区间和目标展示区间不同，动作没完成不能靠目标窗口延长自动补出来。
- Review要求指出哪一个“拥有该问题的输入”要改：故事方向、Script、选定文件、布局/时间关系或组件能力；修改后看相邻衔接及整片。它把“再好看一点”变成可定位的编辑问题。
- Prompt Kit把固定处理、可选方向和当前镜头文字分开，模型/参考媒体/尺寸仍由调用契约负责。文字声称有参考图不等于请求真的绑定了参考图。

### Harness实现核对

`packages/runtime/src/scheduler.ts`的preparations只返回依赖可运行且未在执行/已尝试的命令；资源容量控制并发，跨build轮转。command-failed后停止新增工作，但接收已经发出的调用结果，再提交失败事件。它不意味着任意失败可以盲重试，更不证明缓存命中就代表成片质量。

### 本项目吸收与边界

立即把“目的—文案—证据镜头—切换依据—未决问题”写入轻量创作记录；用真实音频重新检查对应关系。保留当前EditPlan执行格式，不搬入完整SVML、组件包或调度服务。语义锚点自动投影、跨工件依赖追踪仍是后续代码任务，不能将提示词记录描述为已实现编译器。

## 3. OpenMontage：把创意约束传给下游，并让审阅可行动

源码：[纪录混剪scene-director][o-scene]、[taste-direction][o-taste]、[reviewer][o-review]、[checkpoint协议][o-checkprompt]、[checkpoint实现][o-checkcode]、[pipeline-loader][o-loader]、[reference-analyst][o-reference]。

### 提示词中的有效细节

- scene-director明确区分slot的具体画面意图与检索query：前者描述主体、动作、环境、光线，后者是短检索词，并可有直搜/旁侧搜索。不是“高级食物镜头”这种抽象类别。迁移时必须适配当前关键词检索，不假装已经有CLIP向量排序。
- taste_profile把“专业/高级”拆成面向观众的具体表达方向、变化程度、运动强度、信息密度及反例；这些选择贯穿脚本、选片、剪辑和审核，减少每一步自由重写风格。三项1–10刻度是创作参数，不是经过验证的客观质量分数。
- reviewer读本阶段review_focus、成功条件和工件，问题要求有位置与修改建议；发现一类错误时扫描同类问题，而不是只修第一处。这能让下一轮获得有效修改输入。

### 代码与提示词不能混为一谈

`lib/pipeline_loader.py`确实读取stage skill、审核重点和approval字段。`lib/checkpoint.py`的write_checkpoint执行schema、前置阶段和approval检查，保存历史并写新状态；这比仅在提示词里说“记得审核”强。其approval本质仍由调用者提供布尔值，不独立证明人真的看过；代码注释还说明旧completed记录兼容读取。不能把这类门禁称为不可绕过的人工批准证明。

### 必须拒绝的移植

reviewer提示词明确允许两轮后PASS_WITH_WARNINGS；无法提出修法的critical被转成不阻塞的investigation。对包装错版、无依据健康主张或未知授权不能这么处理，未知修法不降低风险。

reference-analyst把motion_clip推断成视频生成，这是不成立的来源判断；真实拍摄也有运动。其每阶段审批、强制资产阶段停顿与当前用户授权及本地低成本工作也不匹配，不照搬。

reviewer引用了一项外部研究来支撑批评质量结论；本轮未独立核查该论文及实验，不把提示词内的引文当作效果证明。

## 4. DramaClaw：受约束输出、证据工具和局部修复

源码：[episode-planner][d-plan]、[episode-reviewer][d-review]、[episode-fixer][d-fix]、[实际分镜图审阅][d-visual]、[全局视频优化][d-global]、[skill数据契约][d-registry]、[resume][d-resume]。

### 不是只加“你是导演”角色

- Planner提示词让模型先查询整体结构、转折、人物关系，再决定边界；代码传入图谱工具和Pydantic输出类型。有效点在于“先取得决定边界需要的证据”，不是小说专用分集规则。对应本项目是先查产品事实与可用动作，再定文案承诺和镜头。
- Reviewer的规则检查负责章节范围/角色等可确定条件，LLM负责叙事和节奏；Report的passed要求score≥8且无critical。数值阈值仅是项目规则，不等于校准过的质量概率或通用营销片标准。
- FixPlan输出具体episode、field、new_value、reason，减少整份重写带来的无关漂移。代码同时保留旧完整重写接口；不能仅凭类名存在断定所有调用路径都使用patch。EpisodePatch.field还是普通字符串，说明字段白名单仍需执行层另行保障。
- 实际visual reviewer将带beat编号的草图网格与简短描述一起提交为BinaryContent，减少“只看文字自我证明”。这只支持分镜整体判断，不证明已看成片动作/听声音；`output_retries=2`主要约束结构化输出重试，不是两轮创作质量优化的证据。

### 不照搬的地方

global_video_optimizer的提示词强制运镜；服务操作和产品包装证据需要静稳画面时，这会破坏任务目标。review_and_fix在审核异常或空返回时保留原prompt并继续，不能被移植为“审核通过”。本项目应明确保留unknown/待查，不写approved。

resume提示词强调真实任务状态、避免重复读/重复启动，这可借鉴；其“即使要求自动完成也每轮只写一步”的服务交互限制与本地CLI任务不一致，不搬过来。

skill_registry包含输入引用、resolved_inputs、幂等键与retryable字段；字段存在不等于所有调用已实施去重或重试策略。本项目已有本地幂等交付，但还缺创作阶段的依赖与恢复记录。

## 5. 花叔艺术动效：把参考转成可测规格，先证明最难片段

源码：[拆解][a-analysis]、[机制][a-mechanism]、[一帧先行][a-frame]、[QA脚本][a-qa]。

有价值的是从“看起来是什么”深入到“怎样发生”：整体接触表定位，转场前后密集帧确定机制，镜内动作清单避免只复刻图片间切换，构图锚点和运动坐标复用。一帧设定解决构图，再用短段确认运动；一次改变一个因素后复测，控制失败成本。

`qa.py`会检查确定性、文字/框景关系及连续帧变化；作者明确把运动比例等写为经验判据。这里的经验来自特定艺术片，不能成为所有宠物食品视频的运动阈值。静止包装说明可能正好更易读。

原文中的特定BPM、比例、角色硬门和作者个人选择不转成通用规则；频谱也不能独立证明素材由代码生成。对本项目应转化为：真实产品细节先看清晰帧，关键操作先看连续短段，确认可用再扩全片。生成的漂亮食物镜头不能冒充真实产品证明。

## 6. Hyperframes：用执行检查兑现具体视觉承诺

源码：[确定性][f-determinism]、[单变量迭代][f-iterate]、[motion-doctrine][f-motion]、[seam-gate脚本][f-seam]、[render阻塞条件][f-block]、[validate运行检查][f-validate]。

- 确定性契约使同一时间可以重复检查同一画面：时间线seek而非自由播放、固定随机性、渲染期间避免漂移的外部数据。固定浏览器/字体/资源也很关键；不能推出跨机器字节完全一致。
- motion-doctrine把衔接写入ledger；seam-gate测方向、速度、可见性重叠和对象几何连续，失败返回非零。`shouldBlockRender`是否阻塞仍取决于strictErrors/strictAll参数，不能将“有lint”理解成默认挡住所有问题。
- 修改第一/最后一秒或重做配音会重新打开相关衔接检查，是对依赖失效的具体定义。
- iterating明确承认lint/check通过仍可能是难看的幻灯片；以实际观看找到具体缺陷，锁定有效部分，用绝对目标修改一个因素。失败时退回简化版本，而非继续堆效果。

本项目吸收“问题→目标→锁定项→最小patch→看相邻边界”的闭环；暂不引入HTML引擎。它的禁止淡化、默认统一左移等是一个动效风格的约定，不是实拍混剪定律。

## 7. ClipForge应该落地的Harness，不是另一套独立系统

宿主负责创作判断；本地工具包负责可确定的证据提取、筛选、校验、执行和记录。无需新增常驻agent服务。

|环节|应由程序保证|应由宿主判断|本轮状态|
|---|---|---|---|
|任务上下文|依赖指纹、候选范围、当前状态与引用文件|本次问题、锁定选择、缺失证据|已有渲染指纹；创作上下文仍为提示词维护|
|参考拆解|局部片段/帧时间、转写来源、分析缓存|观察如何支持机制解释，怎样适配|已有稀疏帧、close-reading指引；H1已实现局部源帧PTS/片段/缓存，见ADR-005；转写待实现|
|选片|业务筛选、时间区间及长度|区间真的证明/说明哪一句，动作完整性|本轮修复区间覆盖；语义判断指引已加强|
|文案分镜|事实版本、时间范围和Schema|主张与事实是否吻合，观众能否理解|现有硬校验+新的段落依据表；语义编译器未实现|
|审阅修复|限定字段、输出/依赖失效、结果记录|具体后果、最小修复假设、实际视听|已有style/等长clip patch；新增critique-repair|
|恢复/成本|已完成状态、缓存、错误类型|下一步最有价值的检查|渲染阶段已有；创作阶段先保存轻量记录|

本轮共新增4份按需指引，并接入9个技能对应入口；没有改动EditPlan v1、自动审批或启动额外模型。资料位于skills下，研究原文不随每次任务加载。

程序优先级（2026-10-09更新）：①局部密集帧/连续片段证据已落地H1；②版本化创作记录与仅相关上下文装配；③事实主张和目标镜头的显式关联校验；④检查结果关联revision、区间和允许patch；⑤创作阶段依赖失效/恢复。先冻结契约再逐项实现。不把这些设计任务写成当前可用能力。

## 8. 用行为和作品检验，而不是数提示词长度

`tests/evals/creative-decisions.json`保存8个合成边界案例。它们是评测输入与预期，不是真实业务事实，也不是已通过的模型评测结果。

对照方法：固定同一原片、事实、模型配置和用户要求；A使用旧提示词，B使用本轮提示词；两边使用相同新运行时，避免把coverage修复算成提示词收益。实际成片用随机顺序给评审者，不暴露版本。工具输出和用户反馈全留存，不只挑最佳例子。

必须分别评估：

- 硬错误：无依据主张、旧包装、授权错用、动作被截断、非授权字段修改，期望0；任何严重项不能由美学分数抵消。
- 任务效果：证据镜头适用率、步骤可理解、开场承诺兑现、字幕/主体冲突、真实视听体验。由可定位问题和人工盲评支持，不用模型给自己的8分代替。
- 收敛：一次修复成功率、同类问题回归数、达到验收所需轮次；记录失败与未决，不能轮次耗尽自动通过。
- 成本：宿主Token、额外模型费用、本地计算时间、人工操作时间、缓存复用；缺某项记未知。效果更好但代价过大也需解释。
- 跨场景：服务片允许静稳清晰，分享片要求真实经历，促销检查适用范围；不要用一套动效审美裁判所有片子。

现有真实素材未提供，因此本轮能声明的是“查到源码机制、强化技能决策指引、修复并回归一个实际缺陷”，不能声明已提高转化率、节省多少Token或达到完整业务质量。

[h-script]: https://github.com/hypit-ai/hypit/blob/7f730abf72fa1e4a543eed8cd1807319d9f18196/skills/hypit/references/creation/script-and-time.md
[h-reference]: https://github.com/hypit-ai/hypit/blob/7f730abf72fa1e4a543eed8cd1807319d9f18196/skills/hypit/references/creation/reference-video.md
[h-broll]: https://github.com/hypit-ai/hypit/blob/7f730abf72fa1e4a543eed8cd1807319d9f18196/skills/hypit/references/playbooks/craft/b-roll.md
[h-review]: https://github.com/hypit-ai/hypit/blob/7f730abf72fa1e4a543eed8cd1807319d9f18196/skills/hypit/references/production/review.md
[h-kits]: https://github.com/hypit-ai/hypit/blob/7f730abf72fa1e4a543eed8cd1807319d9f18196/skills/hypit/references/production/prompt-kits.md
[h-scheduler]: https://github.com/hypit-ai/hypit/blob/7f730abf72fa1e4a543eed8cd1807319d9f18196/packages/runtime/src/scheduler.ts
[o-scene]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/skills/pipelines/documentary-montage/scene-director.md
[o-taste]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/skills/meta/taste-direction.md
[o-review]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/skills/meta/reviewer.md
[o-checkprompt]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/skills/meta/checkpoint-protocol.md
[o-checkcode]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/lib/checkpoint.py
[o-loader]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/lib/pipeline_loader.py
[o-reference]: https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/skills/meta/video-reference-analyst.md
[d-plan]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/src/novelvideo/agents/episode_planner.py
[d-review]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/src/novelvideo/agents/episode_reviewer.py
[d-fix]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/src/novelvideo/agents/episode_fixer.py
[d-visual]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/src/novelvideo/verification/episode_reviewer.py
[d-global]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/src/novelvideo/agents/global_video_optimizer.py
[d-registry]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/src/novelvideo/freezone/skill_registry.py
[d-resume]: https://github.com/dramaclaw/dramaclaw/blob/9822d6fd9ff6d9d2d47d725209b88af75140f676/.hermes/skills/dramaclaw/playbooks/resume.md
[a-analysis]: https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/references/01-拆解.md
[a-mechanism]: https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/references/02-机制.md
[a-frame]: https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/references/03-一帧先行四条路线.md
[a-qa]: https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/scripts/qa.py
[f-determinism]: https://github.com/heygen-com/hyperframes/blob/188475aaf2cc94d05a5a641341cab3020c131f16/docs/concepts/determinism.mdx
[f-iterate]: https://github.com/heygen-com/hyperframes/blob/188475aaf2cc94d05a5a641341cab3020c131f16/docs/prompting/iterating.mdx
[f-motion]: https://github.com/heygen-com/hyperframes/blob/188475aaf2cc94d05a5a641341cab3020c131f16/.agents/skills/motion-doctrine/SKILL.md
[f-seam]: https://github.com/heygen-com/hyperframes/blob/188475aaf2cc94d05a5a641341cab3020c131f16/.agents/skills/motion-doctrine/scripts/seam-gate.mjs
[f-block]: https://github.com/heygen-com/hyperframes/blob/188475aaf2cc94d05a5a641341cab3020c131f16/packages/lint/src/shouldBlockRender.ts
[f-validate]: https://github.com/heygen-com/hyperframes/blob/188475aaf2cc94d05a5a641341cab3020c131f16/packages/cli/src/commands/validate.ts


## 9. Jianying Editor Skill：吸收适配经验，保留业务与审核主线

2026-10-09，按用户要求补充分析。固定提交`32c56928ded4f9e2c2b80e099dc7abb793d2c30b`（提交日期2026-09-11）。32份取证文件清单/哈希在`tmp/harness-research/jianying/manifest.json`；重点函数已核读，部分文件仅读相关段落。没有安装其Skill/依赖、调用远程模型/TTS或访问真实剪映草稿。下述是吸收建议，不代表已接入运行时或改变F13延期约定。

**结论：值得作为F13剪映工程适配的参考，也能为当前H2/H4与音频工作包补充设计判据；不宜整体接管ClipForge生产。** 它的强项是把媒体/字幕/效果编成剪映草稿；已核对的提示词与验收机制不足以单独保证营销事实、选片相关性和成片质量。

### 9.1 提示词与harness的实质取舍

|实际机制与来源|可吸收的部分|ClipForge应怎样改造|
|---|---|---|
|[Playbook](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/docs/agent-playbook.md)按任务选择规则/示例；[最小SOP](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/docs/minimal-command-sop.md)约束扫描、搜效果和执行轮次|先判断任务，再读相关资料；简单任务合并机械调用|H2按问题装配有限上下文，保留失败证据、当前版本和未决项；已有doctor/search/CLI继续复用。不把“最多修一次”当成完成标准|
|[配音字幕](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/core/text_ops.py#L113-L170)逐句生成，按实际音频长度落字幕，首句成功后锁定backend|声音时长驱动时间线，防止中途换声音来源|句段ID关联正文/声音/字幕；缓存键含文本、voice、backend版本、参数；实际听感决定句间停顿。不能固定每句100ms，也不能把句段对齐叫逐词对齐|
|[媒体暂存](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/core/media_ops.py#L57-L93)复制到工程内；[底层素材](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/vendor/pyJianYingDraft/local_materials.py)生成local_material_id|工程交付可选择自包含材料，减小路径失效风险|仍以asset_id/内容SHA256为权威，保存源→副本映射和空间预估；严格模式复制失败阻塞。继续保留轻量交付方案，避免每次渲染复制全库|
|[草稿检查](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/draft_inspector.py#L82-L119)返回轨道/片段/素材数量|生成后再读草稿，比只看写文件成功更可靠|将实际轨道、源区间、字幕/音频时长与EditPlan逐项比对；最后在目标剪映版本打开、播放、导出检查|
|[Clone-first规则](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/rules/core.md)主张复制母版再修改|符合门店版本和不可变母版方向|F11使用允许修改字段、变体ID、差异清单；当前上游并未实现所声明的from_template方法，不能直接照调用|
|[导出器](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/auto_exporter.py#L16-L29)非Windows明确返回unsupported_platform|能力不足显式返回，区别草稿与视频交付|未来F13只做独立输出适配；macOS草稿待手动导出，不改变当前FFmpeg生产交付|

对具体prompt的判断：[影视解说prompt](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/prompts/movie_commentary.md)有“解说/原声段落分工”，适合吸收为音轨意图；但固定60秒、8–12镜和博主人设不适合通用营销/服务视频。[生成规则](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/rules/generative.md)要求秒数浮点，影视prompt却要求HH:MM:SS，builder也只按冒号字符串解析，说明提示词与执行契约未统一。ClipForge继续由Schema定义时间和事实引用，不能只在prompt写“严格JSON”。

### 9.2 已复现与源码明确的限制

可复现命令：`.venv/bin/python tools/research/probe_jianying_reference.py`，结果`tmp/harness-research/jianying/probes.json`。脚本从上述固定提交提取已核读定义，注入最小依赖，在临时目录运行；未导入其应用入口。以下4项均按断言复现，不等同上游全量测试通过。

|问题|证据|对吸收的约束|
|---|---|---|
|源素材已更新却复用旧副本|同一源路径由4字节AAAA改为BBBB；staging仍为AAAA。其复用只看路径MD5+大小|复制缓存必须核对内容哈希，不能复用这套判定|
|禁止覆盖仍触发重建|对load_template注入失败，overwrite=False仍调用create_draft(...allow_replace=True)。底层[create_draft](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/vendor/pyJianYingDraft/draft_folder.py#L66-L100)会删除同名目录；probe仅用mock记录调用，没有执行删除|不可把删目录重建包装成修复；保留原件、新revision、诊断原因；不调用危险默认构造器|
|语义匹配失败静默轮选|缺少chat.py时，3条字幕被分给素材0/1/0；[匹配代码](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/examples/video_transcribe_and_match.py#L90-L118)有模型时也仅传文件名/时长，没有图像或内容标签|保留H1实际证据→H3语义关联；失败返回缺口，不用任意素材补齐生产方案|
|竖片被兼容转码横屏化|实际FFmpeg样例1080×1920、H264/yuv420p，被[normalizer](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/utils/media_normalizer.py#L46-L112)转为1920×1080。1080不被16整除即触发，输出固定横屏padding和30fps|适配按目标画布/原比例和确有证据的兼容需要处理；不得全局固定横屏或擅改时间基准|

另外核对到以下源码差距：

- [SKILL.md](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/SKILL.md)列出`jy_wrapper.py clone/export-srt/apply-zoom`命令；实际[入口](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/jy_wrapper.py#L64-L70)没有参数分发，只尝试创建固定测试工程；JyProject及其mixins中没有from_template。必须对“说明里的命令→实际CLI→产物”做契约检查。
- [movie_commentary_builder](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/movie_commentary_builder.py)按字幕条数均分时间，没有调用配音；无文案片段复制到两条视频轨。不能据此宣称真实音频对齐或恰当混音。`add_media_safe`失败可能返回None，而builder仍继续移动游标、save；属于局部失败可被成功外观掩盖的风险。
- Playbook的检查主要是文件/轨道/字幕存在；[save](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/jy_wrapper.py#L49-L59)没有执行这些完整验收。`audit_timeline`是重复次数提醒，在所核对scripts中未见调用。它们不能代替ClipForge正式片视听审阅、事实校验和批准失效机制。
- [universal_tts](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/universal_tts.py)使用SAMI WebSocket/edge_tts远程服务，前者还读取本机剪映配置/日志标识。Python在本机运行不代表本地语音推理。只吸收声音来源锁定与实测时长，保留现有系统语音/已有录音路径；不接入这些服务。
- [Web录制](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/web_recorder.py)用实时浏览器录屏和完成信号，超时仍可能保存并返回成功，固定1920×1080，未逐帧确定性寻址。保留“动画成为素材”的接口思路，F12仍优先研究Hyperframes的可定位时间渲染；不沿用超时即交付。
- [上游测试](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/tests/test_wrapper.py)包含真实样片暂存，也有空文件、mock网络和mock媒体解析。未在本机跑其完整测试，未验证真实剪映版本可打开/导出；源码的Mac路径支持不等于端到端兼容验收。

### 9.3 对开发计划的影响建议

保持现有H2→H3→H4→H5与MP4+SRT+可复现方案主线。新增建议按以下归属消化，无须新增独立Agent或独立系统：

1. **H2/H4：**记录“用户要求→确有能力→实际调用→产物检查→未决项”的映射；恢复时读取少量状态；增加命令示例可执行性检查，禁止工具返回None/降级结果冒充成功。
2. **F08音频深化：**增加句段级配音/字幕编译，锁定voice/backend、记录实测时长、缓存复用；先验证可懂度、停顿和改一句后其他段不漂移。ASR仍是已有录音的独立问题，不能混为TTS时长对齐。
3. **F11变体：**借鉴母版隔离原则，落为现有计划的受控patch，不依赖上游尚不存在的模板替换API。
4. **F13后续剪映适配：**已审定EditPlan → 编译到新输出目录 → 自包含素材/路径清单 → 反读轨道检查 → 指定剪映版本人工打开/导出 → 与原交付比对。unsupported字段明确拒绝；秒→微秒只在边界转换。先支持切片、原声/独立音轨、基础字幕，特效/转场另验。需要实际目标剪映版本时再确认，不在本轮扩大范围。

H2语义字段、句段音频契约或F13新输出接口均应先另立ADR再实现。本轮只记录评估和可重复取证脚本，没有修改ClipForge运行时、安装技能或改变交付格式。

许可核对：仓库[LICENSE](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/LICENSE)标为MIT；内嵌pyJianYingDraft另有[Apache-2.0文本](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/vendor/pyJianYingDraft/LICENSE)及[修改说明](https://github.com/luoluoluo22/jianying-editor-skill/blob/32c56928ded4f9e2c2b80e099dc7abb793d2c30b/scripts/vendor/README.md)。当前仅分析；后续若复制代码，需分别保留对应许可/归属和修改记录；云端音乐授权不能从代码许可证推定。

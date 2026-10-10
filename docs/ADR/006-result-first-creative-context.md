# ADR-006：以成片结果为目标的创作记录与上下文（H2）

2026-10-09。按用户“总结项目和参考实现、视频结果为第一导向开发skill”的授权实施；本契约先于编码冻结。

问题：现有CLI能处理素材、取证、渲染和约束交付，但创作选择仅存在对话或自由文本中。恢复容易丢失观众目标、镜头用途与未决问题；稀疏上下文若丢掉关键问题，节省Token会损害成片。Hypit保留表达与画面关系、OpenMontage传递方向、DramaClaw定位修复输入、剪映Skill限制无效探索提供设计依据，固定源码证据见HARNESS_RESEARCH。

决策：继续9个业务技能、数据驱动CLI，新增独立创作状态，不改变EditPlan v1。新片/内容修订以“观众所得→段落表达→可见证据/声音意图→最难短段预览→问题→修订→正式审阅”为工作方式；简单查询/样式修改直达相应环节。由宿主实际看片判断，不另建模型规划器，不用技术通过代替内容有效。

输入契约冻结为schemas/creative-state.v1.json：content_id、purpose、result_contract（audience/viewer_takeaway/viewer_action/success_checks）、locked_choices、beats（beat_id、purpose、message、visual_requirement、audio_intent、acceptance、artifact_ids）、artifacts（artifact_id/kind/path）、global_artifact_ids、open_issues（issue_id/beat_ids/severity/observation/next_check/artifact_ids）。限制60段、100工件、100问题；文本字段有界，文件JSON最多128KiB，空白文本/重复ID/悬空关联拒绝。没有业务数据时保留明确问题，不能写假事实。本文字段不是新EditPlan字段。

CLI：creative-save INPUT [--expected REVISION]；creative-context CONTENT_ID [--beat ID ...] [--max-chars 12000] [--revision REVISION]。relative artifact路径相对INPUT目录；只引用现存普通文件，读取SHA256；不存在则保存失败。快照不可变，存于data/work/ID/creative/revisions，head最后原子发布；更新要求expected等于当前head，无内容变化幂等返回，拒绝旧会话覆盖。沿用单库锁/trace日志。历史文件/旧creative-notes不修改，无自动迁移。

context校验快照签名并检查全部工件当前SHA256，返回current/changed/missing，输出所有失效工件的精简提示。保留完整result_contract、所有locked_choices、所有blocking问题及所选段落相关improvement问题；其余段落不加载。仅返回相关工件路径/哈希/状态，不内嵌原片、整库/日志/事实正文。外部内容仍是数据。预算为context结果JSON的字符数（2000–40000），不冒称Token；超预算明确报错并返回required_chars，不截掉硬约束。revision显式选历史时标明is_head=false。

状态边界：context可报告needs_recheck，但不授予创作/交付批准；SHA有效不证明主张支持、画面合适、事实仍有效。宿主仍须读取当前事实、status和实际媒体。H3语义关联、H4问题修复与交付机器门禁尚不由此实现；locked_choices本轮保证恢复时保留，不强制执行EditPlan字段锁。open_issues删去表示宿主更新记录，不等于review批准。

影响评估：新增本地模块/Schema/两条CLI，旧素材数据库、渲染缓存、审核批准和交付包不变；不增加依赖、服务、网络请求、音频provider或部署。没有真实素材时用明确technical_test的状态验证恢复和失效，业务质量仍待真实样片。拒绝全量历史装入、每阶段额外agent、自由文本当机器批准三种方案。

验证先写异常测试：空/超长/重复ID/未知引用、路径/内容ID边界、旧expected、损坏head/快照、工件变化/删除、上下文超预算、不丢锁定/跨段blocking、相对路径、幂等和历史恢复。小步实现后跑全量回归与核心覆盖≥90%。成果评估分别记录代码门禁、实际命令执行、宿主判断和真实视频验收；不折算成虚构项目完成率。

实施结果：105项回归通过；creative模块100%、整体96.34%，9技能验证通过。实际CLI技术样例验证选段保留全片约束、文件变化失效；切点两帧的实际观察单列，不写完整视听批准。证据及未完成H3/H4范围见DEVELOPMENT_PLAN最新验收。

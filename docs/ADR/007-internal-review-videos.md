# ADR-007：业务信息未齐时制作内部审阅片

2026-10-09。用户明确选择“先制作内部审阅版，业务信息后补”。

冻结契约：EditPlan 与 CreativeState 的 purpose 增加 internal_review。其 channel 必须为 internal_review；媒体必须具备该范围的有效授权，不得使用参考片或技术色卡。允许 SKU 尚未登记、包装 unknown，但不允许已知 SKU 冲突、过期授权或 obsolete 包装。原素材元数据保持真实，不把未知改为已确认。

促销内部稿可以不关联 campaign；显式关联的活动、事实仍须通过既有校验。画面中的旧价格、旧门店信息仍需内容审阅，purpose 不证明语义正确。当前六片避免价格板并明确暂缺活动、地址、具体喂养说明。

所有内部稿由渲染器强制烧入全时长“内部审阅 · 信息待确认”，包括没有字幕的计划；渲染可以到 final 规格，但 deliver 一律返回 internal_review_not_deliverable。业务信息齐全后新建 production 计划、重新校验、渲染和审核，不能原地摘除水印即视为通过。

影响评估：只扩展两个 Schema、资格判断、ASS 水印和交付拒绝条件；沿用本地数据驱动 CLI、固定引擎与系统语音，不新增依赖、服务、发布渠道或付费接口。实现哈希使旧缓存自然分版；已有 production 与 technical_test 契约保持。测试覆盖内部稿放行、越权/失效/错 SKU 拒绝、生产仍严格、无字幕水印、交付阻断。

工具检查：本机没有 agent 命令，agent env-check 返回 command not found；使用已锁定的现有环境和 tools/clipforge doctor，未重新初始化环境。导航拼图使用已有 bundled Python/Pillow，项目 .venv 没有 Pillow，不安装新包。

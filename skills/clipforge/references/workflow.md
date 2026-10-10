# 制作流程与契约

使用Python执行本技能普通文件入口`python <技能绝对路径>/scripts/run.py`，可从任意工作目录调用。源码技能向上查找完整工具包；安装副本由同目录`.clipforge-install.json`定位工具包，不能根据安装目录推断仓库位置。启动器使用工具包自己的锁定venv（Windows为`.venv/Scripts/python.exe`，其他平台为`.venv/bin/python`）。同一项目的子技能共享同一个`--data`目录，可复用素材索引；本次选片范围另行限定，不同项目可用不同数据目录隔离。

按需阅读根目录`docs/API.md`以及`schemas/edit-plan.v1.json`。六类场景通过`profiles`命令查询；`recipes/content.json`提供段落用途建议，不强制固定时长或拍摄数量。

## 本次任务输入

制作人员提供或选定一批素材，并用自然语言说明本次目的、主推品、价格及成片要求。宿主从这些输入整理简报和事实记录，已有明确授权和业务信息直接复用，无需用户填写JSON或重复确认。批次来源不自动证明所有文件都是同一SKU或包装仍在售；只在本片需要而依据缺失、或实际画面与提示词冲突时提出具体问题。动作完整性由宿主查看对应片段，确有缺口才请求补拍。

记录当前选定文件对应的asset_id清单，选片和渲染前核对所有源视频均在范围内。当前search/coverage没有批次过滤参数，结果须由宿主筛选；不足时先检查本批未打标素材，用户要求扩展时再查其他批次。该规则属于Skill执行指引，当前CLI没有批次范围的强制校验，不新增EditPlan字段。正式促销所需活动字段仍遵守现有契约；内部审阅可沿用下述业务信息后补流程。

## 操作与产物

1. `scripts/run.py doctor`检查已安装的本地能力。缺引擎时按根目录README初始化，不自动启用额外付费服务。
2. `ingest <素材目录>`只读入库，默认授权/包装未知。依据用户提供的事实批量补齐元数据，不能自行批准。
3. `reference <参考视频> --frames 8`只抽取限量时间码帧组；读实际帧再写观察。稀疏静帧不证明连续动作或热度。需近看时用 `evidence <视频> --start <秒> --end <秒> --fps 4`；短暂事件使用窄区间 `--every-frame`。每段≤10秒/120帧，返回本地HTML、带原声片段及实际源帧时间；没有自动转写或内容理解。
4. `facts <事实JSON>`保存产品与活动依据。确认状态、确认人、来源必须来自实际业务输入。资料中的示例保持pending。
5. `search <关键词> --sku <SKU> --channel <渠道>`和`coverage <需求JSON>`产出候选与缺口。关键词匹配标签，尚无自动向量语义检索。
6. 根据实际证据写符合Schema的EditPlan；宿主完成文案和选片。`validate <计划JSON>`失败时只补必要信息。
7. `render <计划JSON> --mode preview`生成低清预览。按用户请求局部修改；`revise <计划> <patch> <新文件>`保证仅修改指定因素。
8. 预览认可后`render <计划> --mode final`。实际看完整画面、听音频、核对事实和价格，再记录`review <revision> <审阅JSON>`。
9. `deliver <revision>`复检并交付。最终报告实际状态、产物路径、成本及未验项目；不把test_delivered写成生产完成。

复杂新片/内容修订用`creative-save <输入JSON> [--expected <版本>]`保存创作依据，用`creative-context <content_id> --beat <beat_id>`恢复。按需读[result-first](result-first.md)，其字段属于独立创作状态，不能写进EditPlan v1。

## 业务输入样式

元数据例：`{"sku":"用户确认的SKU","packaging":"active","source_kind":"captured","rights":{"status":"confirmed","scopes":["用户指定渠道"],"evidence":"实际授权文件或用户明确授权记录"}}`。这只是结构示例，不是已确认数据。

事实文件包含facts、campaigns数组。事实项：id、sku、value、status、evidence、confirmed_by，valid_until可选。促销还要求完整活动的price、currency、gift、stores、region、starts_at、expires_at、landing。时间戳带时区。不要推断产品存储温度、喂食量或健康效果。

补拍需求：`{"sku":"...","channel":"...","shots":[{"query":"产品特写","duration":2,"purpose":"包装版本证据"}]}`。

审阅记录：reviewer、decision（approved/rejected）、watched、listened、notes、issues。只有实际发生的审阅才能写true。检查工具成功不等于已看过、听过或获得业务批准。

## 边界

v1不支持自动发布、原生编辑器工程、变速/转场参数、自动语音对齐、未配置ASR或大型视觉模型。需要这些能力时先说明当前能力，并完成可执行部分，不编造工具命令。字幕时间来自实际音频/用户记录；缺少精确对齐时保留待审。
# 内部审阅稿

用户允许业务信息后补时，EditPlan / CreativeState 使用 `purpose: internal_review`，brief.channel 也为 `internal_review`。SKU 未登记和包装 unknown 可以保留，但媒体必须有内部审阅授权；活动/事实只要显式引用仍须确认。渲染器全程烧入内部水印，`deliver` 拒绝该用途。通过普通输出路径给用户看片，同时记录待补业务信息；补齐后新建 production 计划重新渲染和审核，不能伪造元数据绕过验证。详见 ADR-007。

# 本地 CLI 与 EditPlan 契约

跨平台入口：`uv run python tools/clipforge.py [--data DIR] COMMAND`（在工具包目录执行）；已有Python也可用绝对路径运行该文件或技能`scripts/run.py`。POSIX保留`tools/clipforge`兼容入口。stdout为UTF-8 JSON；日志送stderr，持久日志含trace_id、阶段、耗时与错误码。成功0、执行失败1、输入错误2。所有路径参数可使用含空格/中文路径，不通过shell插值执行媒体命令。

|命令|输入|输出/副作用|
|---|---|---|
|doctor|无|Python、FFmpeg、固定引擎及可选能力，不安装模型|
|ingest|目录或单个媒体文件；可选元数据JSON|只读媒体、哈希去重、资产清单、SQLite索引；单文件不导入同目录其他文件|
|search|query、sku、channel、limit|有限候选，默认排除未确认授权和旧包装|
|annotate|asset_id、JSON|时间区间标签、来源/证据与版本|
|import-docs|XLSX路径列表|原工作表/单元格/嵌图清单，不把示例当事实|
|import-hub|index.json及旧根目录|旧索引字段保留，媒体缺失明确报告|
|reference|本地视频，最多12帧|探测、导航帧组，time为请求位置，语义观察由宿主补充|
|evidence|视频、start/end、fps或every-frame、size|局部片段、实际PTS帧清单、HTML索引；限10秒/120帧|
|creative-save|创作状态JSON；更新需expected版本|不可变快照、工件SHA256、幂等head；不授予批准|
|creative-context|content_id；可选beat/revision/max-chars|有限上下文、全片锁定项/阻塞问题、工件失效提示|
|facts|已确认事实/活动JSON|版本化事实库；导入不隐式更改确认状态|
|coverage|镜头需求JSON|按匹配标注连续区间长度筛选后取Top5，返回usable_ranges与补拍缺口|
|validate|EditPlan JSON|Schema、时长、引用、授权/活动/事实检查|
|render|EditPlan JSON；preview/final|不可变版本、可核验视频、字幕、封面、阶段缓存|
|revise|EditPlan、受控patch、输出路径|只改字幕样式或指定视频槽，保存变更描述|
|review|作品修订ID、审阅记录JSON|绑定实际媒体哈希；不自动制造人工审阅|
|deliver|作品修订ID|复检后导出MP4/SRT/封面/计划/来源/审核/清单|
|status|可选修订ID|实时有效性、阶段、费用与待处理问题|
|speech|UTF-8文本文件；可选voice|macOS say或Windows System.Speech本地配音、真实时长、可复用WAV；不含逐字对齐|
|profiles|无|六类场景的标签与审核要求|

EditPlan的机器契约位于`schemas/edit-plan.v1.json`及`schemas/edit-plan.v2.json`。显式选择版本；v1继续拒绝v2新增字段。时间使用秒，帧率只允许整数24/25/30/50/60；每个镜头至少0.5秒，长度须为整数输出帧（容差1e-5帧），区间连续拼接。字幕独立于镜头，音轨可以跨镜头。未实现的转场/变速字段直接拒绝。字幕文本不得超过2行、每行按画布/字号保守估计宽度；不截断文字。计划不内嵌绝对素材路径，用asset_id解析根目录映射。

## EditPlan v2 扩展（ADR-010）

下列是附加字段示意，不是独立完整方案。基础字段沿用v1。

```json
{
  "schema_version": 2,
  "overlays": [{
    "id": "detail", "start": 1.5, "end": 3.0, "text": "实物细节",
    "fact_ids": [], "kind": "card", "font_size": 100, "color": "#FFE8A0",
    "box": {"x": 0.1, "y": 0.18, "width": 0.8, "height": 0.12},
    "fade_in": 0.1, "fade_out": 0.2
  }],
  "mix": {
    "ducking": {"reduction_db": -12, "attack": 0.1, "release": 0.3},
    "loudness": {"integrated_lufs": -16, "true_peak_db": -1.5}
  }
}
```

- `clips[].action_window={start,end,evidence}`使用源时间，必须完整落在所选片段内；等长替换有保护的片段时必须重新提供动作依据。工具不证明动作语义。
- `overlays`最多40项、ID唯一，支持`emphasis/card/cta`。start/end使用成片时间；box是归一化区域，x范围0.05–0.95、y范围0.14–0.72，保留顶部水印和底部阅读字幕。正文最多120字符/两行，字号12–160，字宽/高度保守预检；同时间框相交失败。范围不等于主体避让，实际字形和遮挡需看片。花字事实同样纳入验证及业务指纹；SRT只存阅读字幕。
- `audio[].fade_in/fade_out`默认0，非负秒数、总和不超过该轨时长；作用于截取后的音轨，再按start延迟。
- `mix.ducking`仅压低music；reduction_db为−30至0，attack为0.01–2秒，release为0.01–3秒。在旁白开始前attack秒下降、结束后release秒恢复，重叠旁白采用最强一次包络；不会识别句内停顿/音乐重拍，narration本身不被压低。
- `mix.loudness`目标LUFS为−24至−12，真峰为−6至−1dBTP；先对完整混音做第一遍响度分析，再使用实测I/TP/LRA/threshold/offset进行第二遍本地归一化、编码为AAC，最后测量成片。第一遍报告写入渲染目录的`loudness-analysis.json`。偏差超过1LU或真峰高于目标0.2dB、静音/无有效测值时失败。`qa.loudness`含target/measured/status/listening_review；通过不表示听审。所有mix字段均可省略，省略保持旧混音行为。

批次编译：scene显式指定schema_version=2，每个beat.shots都需action_window；`allocate_actions(ranges,frames,fps=30)`先保留动作，再按候选顺序填充至帧总数，不循环/拉伸，容量不足失败。beat.lead_in/tail为0–5秒，省略仍兼容0.12/0.38秒；可以按表达指定留白。beat.cues是相对实测旁白起点的字幕，beat.overlays是相对段落起点的文字层；编译为绝对时间。scene.audio可追加已入库音轨，scene.mix转入计划；scene.content_id可覆盖默认ID。v1继续原等分分配及原帧数计算。

批次仅编译显式选片；没有自动切点、逐词对齐或营销语义评分。现有revise仅支持style/等长clip patch；改overlays/audio/mix要编辑完整方案并重新validate/render。新增字段参与版本指纹，纯字幕/花字/混音变化可复用原片段缓存；不继承旧审核批准。v2切片在固定引擎的现有编码命令中显式限制输出帧数，并核对实际解码帧数，避免转换帧率时切点漂移；v1保留原执行路径。

## 通用业务、审阅及跨平台约束

批次范围：`search`/`coverage`查询共享索引，当前没有批次过滤参数，`validate`也不校验本次选定文件清单。宿主按制作输入记录asset_id范围并筛选候选、核对计划；不能给EditPlan添加未定义的batch字段。用户本次提示词可作为明确业务信息的来源，由宿主保留原话并整理事实记录，无需用户填写JSON；未提供的字段不可推断为已确认。

画面适配：渲染适配器启用固定上游引擎的`aspect_normalize`，采用等比例缩放填满目标画布，再居中裁去超出部分（cover＋center crop），不是拉伸或主体跟踪。旋转依赖FFmpeg默认autorotate；本地单个-90°源片的过滤日志已验证先旋转再缩放裁切，不能据此声明全部旋转情况经过回归。`probe`当前仅保存编码宽高，没有rotation/display尺寸字段；后续横竖屏分类不得直接把编码尺寸当显示尺寸。主体是否被裁掉仍须实际看片。

事实库`facts.json`保存facts和campaigns数组。确认项必须有confirmed_by与evidence；有效期使用带时区ISO8601。计划保存引用的完整记录指纹，事实或资产业务元数据改变均使审核失效。技术样例purpose=technical_test在交付中只能得到test_delivered；production禁止technical_fixture和reference源。

review输入必须包含reviewer、decision=approved/rejected、watched=true、listened=true、notes、issues数组。该命令记录外部已经发生的审阅；调用者不得替审阅人伪造。技术检测不能代替该步骤。正式片与预览分别审阅，避免规格变化遮挡漏检。

外部API费用在本版为0（未调用）；宿主token记null。CPU墙钟时间单列。缓存按真实源哈希、工具版本和有效配置验证。单库写入采用排他锁；并发冲突返回busy，可重试，避免静默覆盖。

跨平台约定见ADR-009。Windows采用第一字节非阻塞文件锁，POSIX采用flock；数据目录建议位于本地，媒体源可独立映射。非UTF-8子进程输出返回tool_encoding，不静默替换JSON内容。创作ID拒绝CON/NUL/COM1等保留名。doctor新增render_capabilities，报告ass/libx264和请求的字体，不把该报告当作中文字体实测通过。

speech省略voice时，macOS选择Tingting；Windows从System.Speech可见的已安装声音中选择，中文文本必须有中文声音，否则voice_unavailable。显式voice按准确名称匹配；不自动下载语言包。Windows脚本仅进程级设置执行策略，不更改系统策略；受组织策略限制时需改用录音。批次编译器的beat可提供audio_file（相对批次JSON）及audio_rights（confirmed、internal_review范围、evidence），此时不调用TTS，按真实音频长度安排镜头。没有audio_file时才使用speech，可由beat.voice指定声音。未验证内容/音质不记录已听过。

coverage区间约束（ADR-004）：有query时各词须出现在同一标注value中，标注连续区间至少达到需求duration；不同时间的关键词不拼接。无query时只证明技术长度。duration为(0,600]内有限数值，不接受bool。usable_ranges是标签证据指向的候选区间，不能代替实际画面审阅。

## 局部时序证据 v1（ADR-005）

`evidence VIDEO --start S --end E [--fps 4 | --every-frame] [--size 640]` 提取最长10秒的局部片段及最多120张实际源帧。采样fps最大60，size为160–1280偶数。区间为相对容器起始时刻的[S,E)，记录实际帧PTS。超出每帧容量时拒绝，不把降采样声称逐帧。

返回evidence_id、artifact（完整清单）、index（HTML）、clip、frame_count、cache_hit；清单保存request/source/clock/frames/files以及视听待审状态。stdout不展开整组帧。局部MP4保留存在的原声但重新编码；时序分析使用清单中的源帧PTS，不能由裁剪片的0秒直接假定准确对应S。


## 创作状态与恢复 v1（ADR-006）

输入以`schemas/creative-state.v1.json`为准，独立于EditPlan。必填result_contract、locked_choices、beats、artifacts、global_artifact_ids、open_issues，以及schema_version/content_id/purpose。保存前可用空artifacts表示尚未选定工件，同时把素材/事实缺口写入open_issues。未确认信息不可伪造。

- `creative-save INPUT [--expected REVISION]`：输入≤128KiB，最多60段/100工件/100问题。路径相对INPUT目录，必须为已有普通文件；记录绝对路径/SHA256。所有ID唯一、关联存在。首次保存不需expected；内容变化必须提供当前head，无变化幂等返回，旧expected拒绝。写快照后原子更新head，进程中断不把半成品发布为成功。
- `creative-context CONTENT_ID [--beat ID ...] [--max-chars 12000] [--revision REVISION]`：缺省全部段落；按需重复beat参数。返回result_contract、所有locked_choices、所有blocking问题、所选段落及相关improvement问题/工件。文件正文和历史日志不自动读入上下文。所有工件都会校验，失效项即使属于其他段也保留精简stale_artifacts提示。
- `max_chars`为返回context对象JSON字符数，范围2000–40000，不包含CLI外层trace_id，不代表Token。超限返回context_budget_exceeded及required_chars，不丢弃硬约束。预算错误时缩小选段/增大显式预算。
- `needs_recheck`在任意工件changed/missing、有blocking问题或选择历史revision时为true；没有这些情况不证明语义或业务批准。`approval`固定not_granted。历史revision仅供检查，不改变head。

快照存于`data/work/<content_id>/creative/revisions/<revision>.json`；签名发现篡改/损坏即拒绝，不覆盖自修复。CLI沿用单库排他锁和结构化日志。旧creative-notes保留，需宿主按实际资料人工整理。当前生产validate/render/review/deliver不自动消费creative记录：语义关联及问题门禁待H3/H4，宿主须按Skills先核对关键问题。文字锁定项在context中完整保留，但本接口不提供EditPlan字段锁执行器。
# 内部审阅用途（ADR-007）

EditPlan / CreativeState 的 `purpose` 支持 `internal_review`。EditPlan 的 `brief.channel` 必须同值；可保留尚未登记的 SKU 和包装 unknown，但授权须有效且包含内部审阅范围，已知错 SKU、obsolete 包装、参考片、技术色卡仍拒绝。促销内部稿可缺 campaign；显式引用的事实与活动仍按原规则验证。

`render --mode final` 表示输出完整规格，不表示业务批准。内部稿始终烧入全时长水印，包括空字幕计划；`deliver` 返回 `internal_review_not_deliverable`。补齐业务资料后新建 production 计划并重新渲染、审核。

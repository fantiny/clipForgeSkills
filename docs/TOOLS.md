# 工具与常用命令

当前执行环境已初始化为根目录.venv，依赖以uv.lock锁定；本地CLI未新增云服务依赖，宿主授权云配音单独记账。文档研究使用原有独立运行时。

## 资料提取

`tools/research/extract_operating_sources.py --out <目录> <源文件...>`只读提取PDF页码、Word段落/表格、Excel工作表与单元格，并记录源文件SHA-256。使用运行时中的pypdf、python-docx和openpyxl；不修改源文件。

## Word交付生成

`tools/research/build_operating_guide.py docs/BUSINESS_CONTENT_GUIDE.md outputs/operating-guide.docx`从同一Markdown正文生成Word交付稿，避免两份内容独立维护。

本机Python：由宿主提供的文档处理Python运行时（本机绝对路径不随仓库分发）。

版面验证使用documents技能提供的render_docx.py和随运行时提供的LibreOffice。中文字体使用本机已存在的Noto Sans CJK SC；字体发现需设置FONTCONFIG_FILE到随运行时提供的fonts.conf，SAL_FONTPATH指向本机字体目录。不得因默认配置失败而静默改用系统LibreOffice。渲染PNG与PDF保存在tmp，仅Word和Markdown作为交付物。

每次正文或样式修改后重新生成并逐页检查。已知问题与检查项见CHECKLIST.md。

## Skills执行工具

- 初始化：`UV_CACHE_DIR="$PWD/tmp/uv-cache" uv sync --frozen`。
- 固定引擎：`uv run python tools/engine/bootstrap.py --source tmp/upstream-source`；无现有检出时省略source。
- 项目安装：`uv run python tools/dev/install_skills.py --host both`。
- 能力检查：`uv run python tools/clipforge.py doctor`；业务命令见API，均返回JSON和trace_id。
- 回归门禁：`uv run python tools/dev/check.py`；执行复杂度、500行限制、技能/宿主安装、pytest和分模块覆盖率。
- 依赖审计：`uv run pip-audit --local`。
- 技术样例：`uv run python tools/dev/smoke.py`，要求本地中文系统声音，不写审核批准。
- 时序证据对照：`uv run python tools/dev/evidence_demo.py`；合成短暂事件，比较8帧导航和局部逐帧，测量像素并输出HTML索引与拼图，不写业务审核。
- 局部证据：`uv run python tools/clipforge.py evidence VIDEO --start 1 --end 2 --every-frame`；普通采样改用`--fps 4`，源文件只读。
- 创作恢复样例：`uv run python tools/dev/creative_demo.py`；用实际CLI保存/恢复技术视频创作状态，并改变自己的方案副本验证失效；不修改原计划，不生成批准。
- 创作状态：`uv run python tools/clipforge.py creative-save INPUT --expected REVISION`（首次省略expected）、`uv run python tools/clipforge.py creative-context CONTENT_ID --beat BEAT_ID`。契约见API和creative-state Schema。
- 技能生成器：`tools/dev/write_skill_bundle.py`用于统一生成受维护的技能说明；手改前注意同步生成器，避免重建覆盖。
- 环境缺口：`agent env-check`命令不存在；以doctor提供真实环境结果，未伪造该命令成功。

CI文件位于.github/workflows/check.yml；仅配置，未执行远程流水线。工具不主动上传原片、资料或作品。

## 提示词与Harness源码取证

`uv run python tools/research/capture_harness_sources.py`从脚本锁定的5个参考提交提取选定提示词及实现，逐文件记录SHA256与错误到tmp/harness-research/manifest.json。部分克隆缺少blob时Git会联网补取；脚本不执行参考项目代码。研究结论见HARNESS_RESEARCH。


剪映Skill专项复核：先只读检出luoluoluo22/jianying-editor-skill的32c56928ded4f9e2c2b80e099dc7abb793d2c30b到tmp/research-excerpts/jianying-editor-skill；运行`uv run python tools/research/probe_jianying_reference.py`。仅执行已审阅定义与临时合成数据，不导入其应用、不读取真实草稿或账户；输出tmp/harness-research/jianying/probes.json。研究文件清单与SHA256另存同目录manifest.json。
# 真实素材内部审阅批次

`uv run python tools/production/build_review_batch.py outputs/review-six-scenes/batch.json --out outputs/review-six-scenes`：按显式文案逐句使用平台系统语音，或使用beat.audio_file指定并经audio_rights授权的录音，测量时长，编译有界镜头区间。`--scenario product` 可只准备一条；加 `--render` 使用已保存的 plan 渲染并复制 MP4、SRT、封面、QA 和运行清单。工具不自动选镜头、循环补时或写审核批准；文案超过选定镜头容量时停止修改该段文案/选片。

scene.schema_version=2启用动作保护分配、显式lead_in/tail、相对旁白cues、相对段落overlays及scene.audio/mix；字段和边界见[API](API.md)。v1仍按原方式分配。渲染声音归一化后会复测最终AAC，数值越界返回失败而非偷偷放行；指标不替代实际听审。首个真实验证批次本地保存在outputs/review-quality-d1/batch.json，可用相同命令重编译（原素材与资产映射仍须存在）。

已有计划批量重渲染：`uv run python tools/production/render_plan_directory.py <批次目录>`。目录须含1–24个`*/plan.json`，先全部validate再逐条render，复制MP4、SRT、ASS、封面、QA、manifest与双遍响度报告；失败立即停止，进度保存在render-progress.json。修正输入后重跑由渲染器验证缓存，不会再次调用云配音服务。缺失/空/超过24个计划的目录在调用CLI前拒绝。

render-progress.json保持成功项数组格式，每次有效批次启动先重置为[]，之后仅登记本轮成功复制的结果。前置校验失败不启动渲染；中途失败保留已完成项，旧媒体文件可能仍在目录中，须核对本轮进度、revision和哈希。该脚本只支持同批次单写者，不并发运行。原有package_review_batch.py专用于旧batch.json制作链，新目录计划批次不自动适配该页面生成器。

公开文档里的`outputs/review-*`、`tmp/review-*`均为脱敏路径示例，不保证本机存在；真实批次路径与源文件映射由本地制作记录维护。公司指导及发布前备份放在`docs/private/`，不会安装到宿主Skill或上传GitHub。

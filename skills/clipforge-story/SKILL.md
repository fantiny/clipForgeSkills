---
name: clipforge-story
description: 依据已确认产品事实、活动和可用镜头编写视频文案与分镜，覆盖种草、科普、分享、促销、服务和门店场景。
---

# clipforge-story

读取profiles及recipes/content.json中选定场景。写给目标观众的具体表达，避免用“先看细节”等制作导览充当购买理由。先明确一个主要用户行动；服务内容可以没有促销。通过library检查素材覆盖，再写文案，避免定稿后才发现没有证据画面。

用户在本次制作提示词中明确给出的主推品、价格和目的就是本次业务输入；宿主整理为简报及所需事实记录，保留对应原话和来源，不要求用户改填JSON或再次确认同一信息。事实通过 `python scripts/run.py facts <JSON>`保存，文案中具体主张关联fact_ids；产品示例、其他SKU的参数及旧活动不继承。只询问本次实际需要且尚未提供的信息；不做促销就不追问活动价格。正式促销仍须满足活动契约，未给出的期限、范围等不可编造。事实校验只证明引用有效，内容是否准确仍须语义审阅。

将用户审定的文案与选片编成根目录schemas/edit-plan.v1.json或edit-plan.v2.json规定的计划，调用 `validate <计划>`。字幕与音频独立于镜头，可跨镜延续。口播过长先改文案或镜头安排，不强制倍速。保持母版与variant_id关系，版本只改指定因素。

复杂作品按 [成片结果与状态契约](../clipforge/references/result-first.md)保存creative JSON，用 `creative-save`留存观众目标、段落依据、锁定项和问题；不要混入EditPlan字段。下一轮用 `creative-context <content_id> --beat <beat_id>`恢复，依赖变化先复查。

AI负责本次创作，本地工具负责验证和执行；不要再调用fvm make/director重复规划。

写文案/选片前读 [具体编辑决策](references/editorial-decisions.md)，保留段落用途、事实支持、镜头区间与切换依据。

参考片机制迁移、动作保留、分层文字或声音处理时读 [关键短段与v2执行边界](../clipforge/references/presentation-v2.md)，先看片/听音建立依据，再编译和检查实际结果。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

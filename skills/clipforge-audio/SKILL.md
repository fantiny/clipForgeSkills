---
name: clipforge-audio
description: 为视频选择原声、已有或经授权生成的配音及音乐，依据真实音频和时间码安排字幕与混音。
---

# clipforge-audio

按成片目标选择真实原声、已有录音或配音。用户已否定系统声音时，不继续批量生成同类声音；根据已有云服务授权和实际能力改用自然度候选，先验证品牌读音、句间衔接和表达。云生成由宿主执行，当前CLI的speech不支持云Provider；按 [配音与音乐接入](references/voice-and-music.md)保存来源、时间码与费用。需要本地语音时执行 `python scripts/run.py speech <文案txt> [--voice <已安装声音名>]`，macOS使用say，Windows使用System.Speech；省略voice按平台选择，中文缺对应声音时不使用其他语言顶替。确认返回的provider和实测duration；不可用时明确返回缺口，不以静音文件伪装配音。

生成/提供的音频通过library入库，注明来源与授权依据。EditPlan.audio指定asset_id、source_start、duration、start、gain_db、role；同一旁白可覆盖多个镜头。对最终实际入库文件重新测量时长后安排画面，不截断；MP3转PCM后可能因编码填充改变时长，不沿用原容器数值。

一句听不清或配音拖长时先修正实际表达/音轨。全片保持已选voice/provider；逐句生成若由宿主操作，要用每段实测时长并听取衔接，不按字数均分；批次工具可按实测句长编译时间，仍不自动决定语义切点或逐词字幕。

本版不自动ASR或逐词对齐；可采用实际听取、用户时间码或云服务返回时间码，保留来源并复核文本与时间轴，不声称服务时间码已自动听审通过。字体变色或只换音乐不得重做配音。BGM使用用户指定且本次用途已获授权的文件，测量选段响度并检查淡变/人声让位；文件名、波峰和数值QA不能证明情绪或卡点。无听音能力时交付明确待听的内审版，不填写listened=true或认定自然度达标。

口播改字或改时长时读 [修复归属与复查范围](../clipforge-review/references/critique-repair.md)，重新核对字幕与画面覆盖，不能只检查音频生成成功。

参考片机制迁移、动作保留、分层文字或声音处理时读 [关键短段与v2执行边界](../clipforge/references/presentation-v2.md)，先看片/听音建立依据，再编译和检查实际结果。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

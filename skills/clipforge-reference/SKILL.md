---
name: clipforge-reference
description: 拆解本地参考视频的开场、信息顺序与节奏，产出带时间码证据的剪辑配方；热度需另有来源。
---

# clipforge-reference

执行 `python scripts/run.py reference <视频> --frames 8`。读取结果reference.json中的实际帧组；对待核实区间执行 `python scripts/run.py evidence <视频> --start <秒> --end <秒> --fps 4`。短暂文字或切点用更窄区间加 `--every-frame`，读取实际帧时间和片段。将观察记录为time_start、time_end、observation、evidence文件与来源，解释另列hypothesis。不要从单帧推断运动方向或用户情绪。

区分可观察结构、可能有效的原因和待验证配方。若用户称为热门片，保留平台链接、采集时间及真实指标；没有热度证据只称参考片。不能把参考视频自动加入商业素材池。交给story的每条建议都应包含证据区间、观察、机制解释、在新片保留的关系和可检查效果。缺转写时不要假造口播。

拆解前读 [近看证据与机制迁移](references/close-reading.md)，将结论转成新片的具体要求；8帧只是导航。

参考片机制迁移、动作保留、分层文字或声音处理时读 [关键短段与v2执行边界](../clipforge/references/presentation-v2.md)，先看片/听音建立依据，再编译和检查实际结果。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

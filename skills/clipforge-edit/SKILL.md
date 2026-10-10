---
name: clipforge-edit
description: 执行审定剪辑方案并局部修改视频、字幕和声音，复用本地合成引擎与镜头缓存。
---

# clipforge-edit

先 `python scripts/run.py validate <计划>`，再 `render <计划> --mode preview`。有缺口时修复对应输入，不开启占位补片。工具将外部审定方案交给固定版本vidmake合成，禁止再次规划素材。

局部修订用 `revise <原计划> <patch> <新计划>`。字幕改色patch为{"style":{"color":"#F2703A"}}；替换镜头用clip.index及完整clip.value，保持时长以锁定其他轨道。生成新版本，检查cache计数和内容差异。有creative记录时先读取对应段落的context，保留用户锁定项；代码当前不自动强制这些文字锁定，必须核对计划差异。

预览通过后 `render <计划> --mode final`，转review。不同规格分别检查裁切、字幕与时长。JSON仅为可复现计划，不宣称是剪映工程。v1拒绝未知转场/变速字段；所需高级效果未实现时说明并保留需求。

内容修订先读 [最小修复与衔接复查](../clipforge-review/references/critique-repair.md)，列出允许变化与锁定字段；对实际渲染结果用 `evidence <输出视频> --start <秒> --end <秒> --every-frame` 检查问题区间及前后衔接，区间超120帧时分段或缩小；源片与成片时间不可混用。

参考片机制迁移、动作保留、分层文字或声音处理时读 [关键短段与v2执行边界](../clipforge/references/presentation-v2.md)，先看片/听音建立依据，再编译和检查实际结果。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

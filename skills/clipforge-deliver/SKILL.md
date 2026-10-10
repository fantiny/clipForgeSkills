---
name: clipforge-deliver
description: 将已审定正式成片打包为MP4、字幕、封面与可复现方案，检查时效、哈希和来源，并记录交付成本。
---

# clipforge-deliver

先读取 `python scripts/run.py status <revision>`核对当前有效性，再执行 `deliver <revision>`。缺审阅、活动失效或素材变化时解释阻塞项，不能沿用旧批准。

输出包包括output.mp4、captions.srt、cover.jpg、plan.json、qa.json、review.json、sources.json、copy.json和delivery.json。source清单用于追溯，不代表附带原始媒体；需要异机复现时用户须提供相同哈希素材并更新根目录映射。

重复导出应返回idempotent=true，不增加使用次数。明确production delivered与technical_test test_delivered区别。费用分别报告额外API、本地耗时与未知的宿主token。本期不发布、不排期、不导出编辑器工程。

交付前有creative记录则读creative-context，核对全部blocking问题与实际review是否一致；存在未解决关键问题不安排生产交付。当前deliver不自动关联creative，宿主必须核对；创作记录本身不是批准。技术通过不证明内容有效。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

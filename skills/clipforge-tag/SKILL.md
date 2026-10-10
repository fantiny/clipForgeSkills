---
name: clipforge-tag
description: 基于本地视频时间码证据进行场景打标，区分技术属性、观察、业务信息和编辑用途。
---

# clipforge-tag

先运行 `python scripts/run.py profiles`选择场景。技术属性由ingest测量；对新标签仅提取必要候选的reference帧组，不逐镜头启动额外模型。可观察主体/动作与SKU/包装/授权分开记录。

使用 `annotate <asset_id> <JSON>`，annotations中的每项必须包含label、value、start、end、source（host/manual/local_model）、evidence、version。证据应为实际看到的帧路径、时间码或转写片段。未知保留未知，静帧不够支持动作时执行 `python scripts/run.py evidence <视频> --start <秒> --end <秒> --every-frame`，限定在最小必要区间。先读返回摘要，再按问题查看帧/片段；不把整组证据无条件塞进上下文。

metadata用于业务确认；metadata确认不能由视觉猜测代替。狗在舔碗不等于喜欢，更不等于改善健康。标签必须帮助实际选片：标出动作完整区间、遮挡/不可读处和可用用途；不能为了字段齐全猜情绪。已有标签重用，新profile只补所需字段。未配置本地模型时明确采用宿主有限证据审阅，不宣称已经自动跑YOLO/ASR/OCR。

标签用于动作选择时读 [片段选择判据](../clipforge-story/references/editorial-decisions.md)。把标签区间限在实际证据能支持的范围，不用整文件时长代替动作时长。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

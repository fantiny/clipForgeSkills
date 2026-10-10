---
name: clipforge-library
description: 只读导入、去重、检索本地视频素材和旧索引，生成制作缺口及补拍清单。
---

# clipforge-library

使用 `python scripts/run.py ingest <目录> [--metadata <JSON>]`，查看new/existing/errors，不把partial说成完整成功。缺授权的素材保留索引但默认不能选用；metadata必须来自实际资料。

依据本次目录或用户选定文件记录对应asset_id范围，包含去重后已有素材。默认仅在该范围选片，用户要求扩展时才引入其他批次。search/coverage当前查询共享库，宿主须核对候选归属；没有批次过滤参数，不能宣称工具已强制隔离。有限搜索无匹配时先检查本批素材与标签，不能直接认定缺素材，也不能用其他批次的结果充当覆盖。

`import-docs <xlsx...>`保留原单元格、图和绘图锚点，示例参数保持pending。`import-hub <index.json> --media-root <旧工作区>`只读兼容旧索引，不改写labels或原视频。

通过 `search <标签词> --sku <SKU> --channel <渠道> --limit 5`查询有限候选。无候选时列缺口或转tag查看有限帧，不能反复全库读取。`coverage <需求JSON>`输出未覆盖的用途、动作、时长与证据要求，按共同需求合并补拍镜头。

补拍按影响成片的缺口排序：必须证明的动作/包装/事实优先，装饰镜头后置。不要只给素材数量，要说明哪些段落已能制作、哪些仍会误导。

不按固定78/115镜生成拍摄工作量。素材用asset_id引用；修订名字不移动原片。

为分镜选素材时读 [片段选择判据](../clipforge-story/references/editorial-decisions.md)。coverage返回usable_ranges，按匹配标注区间筛选后取Top5；仍须确认实际画面支持当前表达。

用Python执行本技能的 `scripts/run.py`（从其他目录调用时用绝对路径）；安装清单定位完整工具包，入口自动使用其锁定venv。命令参数见 `--help`。完整契约和示例按需读 [共享流程](../clipforge/references/workflow.md)。

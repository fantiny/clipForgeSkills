# 技术栈与执行基线

驱动模式：数据驱动，CLI优先。Brief/事实/素材 → 计划 → 原有vidmake合成 → 字幕/独立音轨 → 检查/版本审阅 → 交付。

目录冻结：src/clipforge_skills（本地执行包），skills（共享技能），schemas（版本化契约），profiles/recipes（场景数据），tools（启动/安装/验证），docs（设计与API），.runtime（忽略的固定提交引擎），.clipforge（忽略的本地数据），tmp（验证产物）。

ADR-010首轮质量能力沿用锁定依赖与固定引擎，未添加模型/服务。ASS负责有限文字层，FFmpeg volume/afade/loudnorm负责包络和响度。选择旁白时间窗让位，优点是无需检测模型且确定性可测，限制是句内静默不自动释放；没有第二个实现，不引入Provider。仍为数据驱动、CLI优先：已审源动作/实测旁白→v2计划→校验→原片缓存→文字及混音→最终AAC复测→视听审阅。当前实测macOS/Python3.13.12/FFmpeg6.0；新增测试已加入Windows/Ubuntu CI清单，远端执行另验。

使用 uv 0.12.7 官方脚手架。Python 3.13.12 已安装，满足上游 >=3.11；本包锁定验证为3.13系列。标准库sqlite3/json/hashlib/subprocess负责存储和执行；jsonschema校验契约，openpyxl只读旧表，PyYAML支持上游配置。实际依赖版本以uv.lock为准。测试使用pytest及coverage，新增依赖执行pip-audit。

外部引擎：fantiny/clipforge@77a7e73e1f898581d325f3070b574ea0894d8a76 的vidmake，进程隔离调用compose_stage；不调用内部director/script，不加载机器local.yaml。FFmpeg/ffprobe使用已安装6.0，doctor记录路径、版本和能力。该组合仅声明本机验证范围，不代替上游官方兼容矩阵。

宿主：[Codex项目技能目录](https://learn.chatgpt.com/docs/build-skills)为.agents/skills，[Claude Code](https://code.claude.com/docs/en/skills)为.claude/skills。安装器将同一skills源安装为受管理副本，入口指向完整工具包的锁定环境；不改变全局配置，不启动独立服务。更新源码后重跑安装器同步指引。

取舍：SQLite替代新增数据库服务；FFmpeg+原有合成替代完整引入其他项目运行时；额外模型默认不调用。Hyperframes和原生编辑器导出未锁定版本前不自动执行或宣称支持。

版本与兼容依据：[Python3.13](https://docs.python.org/3.13/)、[uv](https://docs.astral.sh/uv/concepts/projects/init/)、上游pyproject.toml，依赖包自身requires-python由uv解析校验。二进制能力以实际doctor和集成样例为准。

CI配置GitHub托管Ubuntu和Windows runner，按[checkout官方说明](https://github.com/actions/checkout)与[setup-uv官方说明](https://github.com/astral-sh/setup-uv)锁定Action提交（见workflow）；uv固定0.12.7。Windows CI媒体包锁定[Chocolatey FFmpeg 9.0.2](https://community.chocolatey.org/packages/ffmpeg/9.0.2)，Ubuntu使用runner仓库版本；doctor保留实际版本及滤镜/编码器信息。引擎无关检查与依赖私有引擎凭据的集成检查分开，执行结果及未验项见开发计划。

局部时序证据沿用同一FFmpeg/ffprobe与Python标准库；无新增依赖。输入时钟使用copyts/start_at_zero，真实帧PTS由showinfo记录；契约及官方来源见ADR-005。采样与逐帧是同一证据工具的两种选择方式，不引入新服务或模型Provider。

H2创作状态复用已锁定jsonschema与标准库，快照+原子head保存在原有data/work下；context读取SHA256和有限元数据。无新数据库、模型、服务或部署。ADR-006冻结独立Schema，不改变EditPlan、渲染缓存和交付包。

## Windows原生兼容性审计（2026-10-10）

审计基线：`0e135cd148a90402ddd571025b78e59b63d15b9d`，上游固定引擎仍为`77a7e73`。以下表格记录修复前问题；后续已按ADR-009实施启动/安装/锁/编码/单文件导入/拼接/声音来源适配，不应将历史问题清单当成最新实现状态。修复验证结果见开发计划。WSL运行不能替代原生验收。原审计探针记录在本地`tmp/windows-audit/probes.json`，不随仓库分发。

| 优先级 | 代码位置 | 问题、影响与证据 | 修复方向（尚未实施） |
|---|---|---|---|
| P1 启动阻断 | `src/clipforge_skills/core.py:4,69` | 顶层导入Unix专用fcntl，CLI导入即失败，doctor也无法运行；模拟缺少模块已复现ModuleNotFoundError | 保持现有单写者锁契约，增加Windows锁实现；验证竞争、异常释放、进程退出后的重新获取 |
| P1 启动阻断 | `tools/clipforge:8`；`tools/production/build_review_batch.py:18`；`tools/dev/creative_demo.py:49` | 写死`.venv/bin/python`；子进程直接执行无扩展名脚本。Windows venv使用Scripts目录，原生CreateProcess不能依赖Unix shebang | 统一显式Python/已安装CLI入口；同步所有子进程、Skill命令和PowerShell安装说明 |
| P1 安装阻断 | `tools/dev/install_skills.py:17–22`；Git中的27个链接 | core.symlinks=false检出后，run.py成为仅含链接目标的文本，实测SyntaxError；安装器将已有宿主链接文本当冲突拒绝。创建链接还受Windows权限/开发者模式约束 | 提供无需符号链接权限的普通文件入口及可更新安装方式；只识别修复本项目链接占位文件，不覆盖其他技能 |
| P1 跨盘安装 | `tools/dev/install_skills.py:22` | C盘工具包安装到D盘项目时，os.path.relpath无法计算；ntpath实测ValueError | 不依赖跨盘相对路径；纳入工具包与目标项目不同盘符的安装验收 |
| P1 中文文件/进程通信 | `tools/engine/run_stage.py:11`；`core.py:86`；`evidence.py:51`；制作/打包/生成/检查脚本 | 多处read_text/write_text及text=True没有明确编码。Python3.13非UTF-8 Windows环境下可能读错UTF-8配置或解码FFmpeg输出失败；中文Skill按cp1252/cp936读取均已复现UnicodeDecodeError | 文本工件统一UTF-8；宿主/子进程JSON建立明确编码约定；工具日志按输出编码处理，不用忽略解码错误掩盖JSON损坏 |
| P1 六场景制作缺能力 | `audio.py:13–25`；`tools/production/build_review_batch.py:49` | speech只有macOS say，批量脚本无条件指定Tingting，无法在原生Windows生成同一批片。已有录音可用于基础剪辑，这不是所有音频输入都不支持 | 批量制作支持已有音频；若要求Windows本地TTS，再冻结Provider契约、实现与实测中文声音/缓存/时长 |
| P2 旧库导入 | `src/clipforge_skills/importers.py:117` | 每个旧素材创建symlink，没有无权限降级；即使安装器修好仍会在import-hub失败 | 支持直接登记指定文件，保持原片只读，避免为兼容而复制整个素材库 |
| P2 文件名 | `core.py:112`；`creative.py:13` | safe_id接受CON等设备名，随后直接作为创作目录。已确认safe_id('CON')通过且ntpath.isreserved为true | 统一拒绝保留名并测试；评估大小写不敏感目录的ID冲突，避免不同作品混用 |
| P2 字幕可读性 | `captions.py:19`；`media.py:37` | 默认Arial Unicode MS但未检查字体存在/中文覆盖；doctor只报告工具路径和版本，未验证libass/libx264。具体回退字体与是否缺字须Windows实测 | 明确中文字体来源和选择，检查编码器/滤镜，并渲染检查中文、标点、水印；不能以解码成功代替可读性 |
| 验收缺口 | `.github/workflows/check.yml:7,36`；`tools/dev/check.py:24` | CI仅Ubuntu，检查脚本要求链接resolve完全一致；原测试通过不证明Windows可安装或出片 | Windows原生CI加入默认无链接安装、中文/空格/跨盘、录音渲染、局部修改、交付及锁测试；保留macOS/Linux回归 |

上游合成还需覆盖：`feedcut_compose/__init__.py:483–486`以默认编码写绝对路径concat清单，未转义路径中的单引号；非UTF-8路径、Windows盘符/UNC和含单引号目录需针对固定引擎验证。当前适配器每个镜头也会经过这段上游concat。不能只检查本仓库最终拼接：本仓库`render.py:127`已用UTF-8相对文件名，字幕滤镜也使用相对`captions.ass`，这两处没有直接嵌入盘符的问题。长路径及SMB源文件＋本地缓存也需实机验收，不能从pathlib的使用推导为已支持。

实施顺序建议：先冻结启动/安装/锁/编码的跨平台约定并记录ADR → 打通Windows使用已有音频的MP4＋SRT＋方案闭环 → 验证中文字幕和固定上游引擎 → 按业务要求补Windows离线TTS → 双宿主实机验收。兼容修复不改变Brief/EditPlan业务含义，也不把macOS挂载路径直接当Windows共享路径；素材迁移使用已有root映射机制。本轮未选择新依赖或改变引擎版本。

官方依据：[fcntl仅Unix](https://docs.python.org/3.13/library/fcntl.html)、[venv平台目录](https://docs.python.org/3.13/library/venv.html)、[Windows符号链接权限](https://docs.python.org/3.13/library/os.html#os.symlink)、[Git core.symlinks](https://git-scm.com/docs/git-config#Documentation/git-config.txt-coresymlinks)、[Python文本编码](https://docs.python.org/3.13/library/io.html#text-encoding)、[子进程编码与执行](https://docs.python.org/3.13/library/subprocess.html)、[Windows文件名限制](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)。

## 授权云音频与本地执行的边界（2026-10-10）

当前沿用已有音频入库与跨镜音轨契约：宿主可按用户授权调用云TTS，CLI speech仍仅本地系统语音。云方案自然度是待听的选择标准，不保证达标；系统语音无需网络但本轮被用户否定其听感。没有新增Provider框架或依赖，不将临时MiniMax调用写成通用已完成组件。生成缓存、时间码转换与成本汇总执行器需下一轮契约冻结后实施；本次先固化可复用指引。双遍loudnorm沿用FFmpeg，相同混音图分析后归一化，最终编码复测；多一次本地音频分析，不重复合成配音。

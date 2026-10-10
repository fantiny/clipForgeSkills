# ADR-009：Windows原生启动与媒体执行

日期：2026-10-10。状态：已实施；Windows原生组件CI通过，私有引擎全链路及桌面视听验收待完成。

## 变更影响评估与冻结范围

用户要求仓库兼容Windows并继续修复。基于STACK审计，改动触及工具入口、技能安装、库锁、文本编码、旧素材导入、音频来源与CI；不改变EditPlan、事实确认或交付批准规则。原片只读，不新增联网模型或运行时依赖，不修改固定上游检出内容。

1. CLI统一提供普通Python入口，显式选择本仓库venv（Windows Scripts/python.exe，其他平台bin/python）；子进程使用sys.executable及UTF-8模式，不依赖shell/shebang。技能run.py为普通文件，源码模式查找仓库，安装模式读取本技能安装清单中的绝对工具包位置。
2. 安装采用受管理副本，不要求管理员、开发者模式或同盘符。清单记录所有安装文件哈希与工具包来源；更新前核验全部目标，遇用户修改或其他技能拒绝覆盖。只迁移可准确识别的本项目旧链接/链接占位文本。宿主安装目录不再以符号链接跟踪；生成器与安装器同步。复制的是技能指引，运行时仍使用完整工具包，重新安装更新指引。
3. 保持非阻塞单写者语义。POSIX flock与Windows msvcrt.locking锁第一字节两实现按平台选择；竞争返回busy，其他系统错误保留。异常退出后由OS释放，不用删除锁文件模拟解锁。数据目录建议本地，SMB仅作原片源。
4. 工件及JSON协议固定UTF-8；子进程UTF-8解码失败显式报错，不悄悄忽略。进程启动设置Python UTF-8模式。ID额外拒绝Windows保留名，不改写已有业务ID。
5. 旧库导入直接登记单文件，复用原哈希/根映射逻辑，移除临时symlink。固定引擎只在进程适配层替换concat：工作目录内相对安全文件名、UTF-8清单，避免盘符/引号嵌入清单；适配层哈希进入已有缓存签名。
6. speech保留macOS say，Windows使用系统System.Speech本地语音；按平台选择provider，显式voice缺失时报错，无可用声音不生成静音。批次允许每段提供已授权录音，测量真实时长；无录音才调用本地TTS。不默认下载声音、模型或启用付费API。
7. 默认字体按平台选择（Windows Microsoft YaHei，macOS Arial Unicode MS，Linux Noto Sans CJK SC）；doctor报告字幕滤镜/编码器能力。字体实测与听感仍须原生环境验证，不保证宿主字体回退的排版一致。

## 验证与边界

先补输入边界及异常用例，再分步实现并运行既有全套回归。新增：无链接检出/安装/更新保护、不同目录启动、中文及空格路径、跨进程锁与退出恢复、保留名、录音路径、编码、上游concat及缓存。CI加入Windows原生无引擎测试；完整引擎集成继续要求已有私有引擎访问凭据，不上传用户凭据。未实际执行的Windows视听、UNC/长路径、中文系统语音必须标为待验。

官方依据：[msvcrt锁](https://docs.python.org/3.13/library/msvcrt.html#msvcrt.locking)、[subprocess编码](https://docs.python.org/3.13/library/subprocess.html)、[系统语音WAV输出](https://learn.microsoft.com/en-us/dotnet/api/system.speech.synthesis.speechsynthesizer.setoutputtowavefile?view=netframework-4.8.1)。版本沿用Python3.13与uv.lock；不增加Provider框架，只有当前确实需要的平台分支。

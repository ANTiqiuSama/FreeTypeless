# FreeTypeless

**自由、开源的 Windows AI 语音输入（Typeless 平替）**：在任何软件里按住热键说话，松开后把整理好的文字直接输入到光标处。语音识别和润色都用 **小米 MiMo** 的 API（推荐 Token Plan），不需要本地 GPU。

> 按住 `右 Ctrl` → 说话 → 松开 → 干净、带标点、已排版的文字出现在光标处。

## 功能（对标 Typeless）

| Typeless 功能 | FreeTypeless |
| --- | --- |
| 全局按住说话、任意应用输入 | ✅ 默认 `右 Ctrl`，可改任意键/组合键；**轻点**进入免提模式，再按一次结束；`Esc` 取消 |
| 去口头禅（嗯、啊、那个） | ✅ |
| 去重复、结巴 | ✅ |
| 说错改口只保留最终意思（“不对，是四点”） | ✅ |
| 自动排版（口述“第一、第二”→ 列表） | ✅ |
| 个人词典 | ✅ 词典 + 强制替换规则 |
| 不同应用不同语气 | ✅ 自动识别微信/QQ/飞书/邮件/IDE/终端/AI 聊天页面，也可以按 exe 自定义 |
| 边说边翻译 | ✅ `F9`，目标语言可选 |
| 选中文字后用语音改写（Speak to edit） | ✅ `F8`：选中文字说“翻译成英文”“改得更礼貌”“缩短一半” |
| Ask anything | ✅ `F8` 时不选中文字 = 语音提问，弹窗回答，可一键插入 |
| 中英混说、方言 | ✅ MiMo-V2.5-ASR 支持中英混合与粤语、吴语、闽南语、四川话等 |
| 历史记录 | ✅ 托盘 → 历史记录（同时保留原始识别文本） |
| 隐私 | ✅ 开源、本地运行；API Key 用 Windows DPAPI 加密保存；录音只发给你配置的 MiMo 接口 |

另外还有：润色失败自动退回原始识别（不丢字）、防“AI 回答了你的话而不是记录”的安全阀、粘贴后恢复剪贴板（包括图片）、临时文本不进 Win+V 历史、长录音自动切片并发识别、开机自启、单实例。

## 为什么用 MiMo-V2.5-ASR + MiMo-V2.6-Flash

Token Plan 支持的音频相关模型有两类：

1. **`mimo-v2.5-asr`（专用语音识别，默认）**：中英双语 + 方言，抗噪、远场、多人重叠说话依然稳定，专有名词/术语识别好，**自动带标点**。Token Plan 按音频时长计费：**每小时音频 3000 万 Credits**，Max 套餐 9840 亿 Credits ≈ **3 万多小时**，日常听写基本用不完。
2. **全模态模型（`mimo-v2.6-flash` / `pro`，可直接听音频）**：可以“一步”完成听写+润色，但它是通用对话模型，逐字准确率和稳定性不如专用 ASR，也更容易“回答”你的话。

所以默认管线是 **ASR（逐字准确）→ `mimo-v2.6-flash`（关闭深度思考，快且便宜）润色**。一次普通听写润色约几百 token，约十万 Credits 量级，可忽略不计。设置里可以切换：

- `asr+llm`：推荐，最准，Typeless 体验
- `asr_only`：只识别不润色，最快
- `omni`：全模态一步到位（实验）

> 注意：MiMo 官方公告旧的 `mimo-v2.5` / `mimo-v2.5-pro` 模型 ID 将在 2026-10-21 失效，本项目默认使用 `mimo-v2.6-*` 系列。

## 安装

### 方式一：下载 exe（推荐）

1. 打开 [Releases](https://github.com/ANTiqiuSama/FreeTypeless/releases/latest)，下载 `FreeTypeless.exe`。
2. 双击运行（Windows SmartScreen 提示时点“更多信息 → 仍要运行”）。
3. 首次启动会弹出设置：填入 Token Plan 控制台里的 **API Key（tp-xxxx）** 和 **专属 Base URL**（默认 `https://token-plan-cn.xiaomimimo.com/v1`），点“测试连接”，再点“保存”。

### 方式二：PowerShell 一键安装

```powershell
irm https://raw.githubusercontent.com/ANTiqiuSama/FreeTypeless/main/scripts/install.ps1 | iex
```

它会把 exe 装到 `%LOCALAPPDATA%\Programs\FreeTypeless`，并创建桌面和开始菜单快捷方式。想从源码安装（自动用 winget 装 Python 3.12）：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/ANTiqiuSama/FreeTypeless/main/scripts/install.ps1))) -FromSource
```

### 方式三：开发者

```powershell
git clone https://github.com/ANTiqiuSama/FreeTypeless.git
cd FreeTypeless
py -3.12 -m venv .venv; .\.venv\Scripts\activate
pip install -e .[dev]
python -m freetypeless --set-key tp-xxxx --set-base-url https://token-plan-cn.xiaomimimo.com/v1
python -m freetypeless --test          # 测试连接
python -m freetypeless --transcribe a.wav
python -m freetypeless                 # 启动
```

## 使用

| 操作 | 默认热键 |
| --- | --- |
| 听写 | 按住 `右 Ctrl` 说话，松开输入 |
| 免提听写 | 轻点 `右 Ctrl`，说完再按一次 |
| 指令：改写选中文字 / 语音提问 | 按住 `F8` |
| 边说边翻译 | 按住 `F9` |
| 取消 | `Esc` |

托盘菜单：设置、历史记录、重新粘贴上一条、复制上一条、重新处理上一段录音、AI 润色开关、退出。

配置和日志在 `%APPDATA%\FreeTypeless\`（`config.json`、`app.log`、`history.jsonl`、`recordings\`）。

## 常见问题

- **在管理员权限的窗口里没反应**：Windows 不允许普通程序向管理员窗口发送按键。可以“以管理员身份运行” FreeTypeless。
- **某些终端/游戏里 Ctrl+V 不生效**：设置 → 高级 → 粘贴方式改为 `shift_insert` 或 `type`。
- **笔记本 F8/F9 要按 Fn**：在设置 → 热键里点“录制”换成别的键，例如 `alt_r`、`caps_lock`、`ctrl+shift+space`。
- **VS Code 里没选中文字也被当作“选中”**：VS Code 默认无选区时 Ctrl+C 会复制整行，可关闭 `editor.emptySelectionClipboard`。
- **鉴权失败**：Token Plan 的 Key（tp-）必须搭配 Token Plan 的 Base URL；按量付费的 Key（sk-）用 `https://api.xiaomimimo.com/v1`。
- **杀毒软件误报**：PyInstaller 打包的单文件 exe 偶尔被误报，可改用源码安装方式。

## 参考的开源项目

- [cjpais/Handy](https://github.com/cjpais/Handy)（Rust/Tauri，离线 Whisper/Parakeet，按键说话）
- [OpenWhispr/openwhispr](https://github.com/OpenWhispr/openwhispr)（Electron，本地/云端模型，听写+AI 代理）
- [tover0314-w/opentypeless](https://github.com/tover0314-w/opentypeless)（开源 Typeless/Wispr Flow 平替）
- [HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline)（Windows 中文离线语音输入，按住 CapsLock）

## 开发

```
freetypeless/
  app.py       主程序与线程编排、CLI
  hotkeys.py   全局热键状态机（按住/轻点免提/组合键升级/Esc 取消）
  audio.py     录音、重采样、WAV、长音频切片
  mimo.py      MiMo OpenAI 兼容接口（ASR / Chat / 全模态）
  prompts.py   提示词与应用场景识别
  pipeline.py  录音 → 文本的处理管线（含兜底与安全阀）
  winutil.py   前台窗口、剪贴板备份恢复、模拟粘贴、DPAPI、自启
  ui.py        浮窗、设置、历史、问答窗口、托盘
```

`python -m pytest -q tests`；CI 会在 Windows 上跑单元测试和真实 UI/托盘/键盘钩子/剪贴板冒烟测试，然后用 PyInstaller 打包发布到 Releases。

MIT License

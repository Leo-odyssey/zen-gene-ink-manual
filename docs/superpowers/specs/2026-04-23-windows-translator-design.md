# Windows 智能翻译与优化工具 — 设计文档

**日期：** 2026-04-23
**状态：** 已批准，待实现

---

## 概述

一个常驻 Windows 系统托盘的轻量应用，通过全局快捷键在任意输入框（Outlook、WhatsApp 等）中触发，自动检测输入语言，调用 Claude API 对文本进行英文优化或中译英翻译，在悬浮窗展示结果，用户确认后一键替换输入框内容。

---

## 功能范围

1. **英文优化模式**：检测到纯英文时触发，修正拼写/语法错误，并按场景（邮件/日常）改写为地道表达
2. **翻译模式**：检测到含中文字符（纯中文或中英夹杂）时触发，翻译为地道英文
3. **场景切换**：悬浮窗内可手动切换邮件/日常场景，自动根据当前窗口推断默认值
4. **一键替换**：用户确认后自动替换输入框原有内容

---

## 技术栈

| 组件 | 技术 |
|---|---|
| 语言 | Python 3.11+ |
| GUI | PyQt5 |
| 全局快捷键 | `keyboard` 库 |
| 窗口检测 | `pywin32` |
| AI 后端 | Claude API（`anthropic` SDK） |
| 模型 | `claude-haiku-4-5-20251001` |
| 打包 | PyInstaller（单 exe） |

---

## 整体架构

```
用户在任意输入框打字
       │
  按快捷键（Ctrl+Shift+Space）
       │
  [后台 Python 进程 - 系统托盘应用]
  ├── 检测当前窗口 → 推断默认场景
  ├── 模拟 Ctrl+A + Ctrl+C 读取文本
  ├── 语言检测 → 翻译/优化模式
  ├── 调用 Claude API（流式）
  └── 弹出 PyQt5 悬浮窗
             │
       用户确认/取消
             │
  ├── 确认：模拟 Ctrl+A + Ctrl+V 写回
  └── 取消：关闭窗口，恢复原剪贴板
```

---

## 模块结构

```
translator-app/
├── main.py              # 入口：初始化各模块，启动 Qt 事件循环
├── tray.py              # 系统托盘图标与右键菜单
├── hotkey.py            # 全局快捷键注册与监听
├── window_detector.py   # 检测当前聚焦窗口，推断默认场景
├── clipboard_io.py      # 读取/写回输入框内容（模拟按键 + 剪贴板）
├── language.py          # 语言检测（中文字符判断）
├── claude_client.py     # Claude API 封装，含四套 prompt
├── popup.py             # PyQt5 悬浮窗 UI
└── config.py            # 配置读写
```

---

## 完整触发流程

```
按下快捷键
    │
    ├─▶ window_detector → 获取窗口名 → 推断默认场景（邮件/日常）
    └─▶ clipboard_io → 保存原剪贴板 → Ctrl+A + Ctrl+C → 读取文本
              │
         文本为空？──是──▶ 托盘图标闪烁，退出
              │ 否
              ▼
         language.py 检测
         ├─ 含 [一-鿿] → 翻译模式
         └─ 纯英文 → 优化模式
              │
              ▼
         claude_client.py → 流式调用 Claude API
              │
              ▼
         popup.py 显示悬浮窗（流式边加载边显示）
         ┌─────────────────────────────┐
         │  [场景：邮件 ⇄ 日常]        │
         │  ───────────────────────    │
         │  原文（灰色）               │
         │  建议（白色加粗）           │
         │  ───────────────────────    │
         │   [✓ 替换]    [✗ 取消]     │
         └─────────────────────────────┘
              │
         ┌────┴────┐
       确认       取消
         │         │
         ▼         ▼
    Ctrl+A+Ctrl+V  关闭窗口
    写回输入框     恢复原剪贴板
    恢复原剪贴板
```

**补充：手动选中模式**
对于禁用 Ctrl+A 的特殊输入框，用户可手动选中文字后触发快捷键，程序优先使用选中内容（Ctrl+C 读取选中部分）。确认替换时只用 Ctrl+V 写回，仅替换选中区域，不影响输入框其余内容。

**场景切换行为**
用户在悬浮窗点击场景切换按钮后，立即以新场景重新调用 Claude API，结果实时更新到悬浮窗，无需额外点击。

---

## Claude API Prompt 设计

### 系统 Prompt（所有请求共用）

```
You are a native English speaker who writes naturally in both
casual and professional contexts.

In casual mode: write like a real person texting a friend —
use everyday contractions, informal expressions, and common
internet shorthand where it fits naturally (e.g. lol, lmk,
omw, ngl, tbh, imo). Never sound stiff or robotic.

In professional mode: write clear, polished business English
— friendly but formal, using common everyday words. Avoid
jargon, overly complex vocabulary, or stiff phrases like
"please do not hesitate to contact me."

Rules for all responses:
- Return only the final text, no explanations, no quotes
- Preserve the original meaning
- Fix all spelling and grammar errors
```

### 用户 Prompt 模板

| 模式 | 场景 | Prompt |
|---|---|---|
| 优化 | 邮件 | `Professional mode. Improve this English for a business email:\n{text}` |
| 优化 | 日常 | `Casual mode. Improve this English for a chat message:\n{text}` |
| 翻译 | 邮件 | `Professional mode. Translate to English for a business email:\n{text}` |
| 翻译 | 日常 | `Casual mode. Translate to English for a chat message:\n{text}` |

### API 参数

- 模型：`claude-haiku-4-5-20251001`（低延迟，适合实时场景）
- 流式输出：开启
- max_tokens：512

---

## 窗口-场景默认映射

| 窗口标题关键词 | 默认场景 |
|---|---|
| `outlook`, `mail` | 邮件 |
| `whatsapp` | 日常 |
| 其他 | 日常 |

用户可在设置界面自定义此映射表。

---

## 错误处理

| 情况 | 处理方式 |
|---|---|
| 输入框内容为空 | 不触发，托盘图标短暂闪烁 |
| API 超时（>8秒） | 悬浮窗显示"请求超时" + 重试按钮 |
| API Key 未配置 | 首次启动弹出设置引导 |
| API Key 无效/余额不足 | 悬浮窗显示具体错误信息 |
| Ctrl+A/Ctrl+C 读取失败 | 悬浮窗提示"请手动选中文字后再触发" |
| 用户关闭悬浮窗时 API 仍在请求 | 取消请求，恢复原剪贴板 |
| 快捷键与其他软件冲突 | 注册失败时托盘提示，引导用户在设置中更换快捷键 |

---

## 配置文件

位置：`%APPDATA%\TranslatorApp\config.json`

```json
{
  "api_key": "sk-ant-...",
  "hotkey": "ctrl+shift+space",
  "window_scene_map": {
    "outlook": "email",
    "whatsapp": "casual"
  },
  "startup_with_windows": true
}
```

API Key 仅存于当前用户目录，不上传任何用户文本内容。

---

## 托盘菜单

- 设置（API Key / 快捷键 / 窗口映射）
- 暂停 / 恢复监听
- 退出

---

## 打包

使用 PyInstaller 打包为单一 `.exe`，用户双击即可运行，无需安装 Python 或任何依赖。

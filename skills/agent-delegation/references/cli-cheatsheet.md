# CLI 說明入口

一般新派工先執行 `python3 <skill-dir>/scripts/dispatch.py` 查看總覽，再讀需要的子指令 `--help`。工具順序、層級數、模型限制與推理強度由 [policy.json](../scripts/policy.json) 提供。

Windows 使用 `py -3 <skill-dir>/scripts/dispatch.py`，需要 Python 3.9+ 與 Windows 10+。平台限制、狀態目錄與 CLI 包裝格式見腳本的 `--help` 及 `dispatch --help`。

| 工具 | 原生說明入口 |
| --- | --- |
| OpenCode | `opencode --help`、`opencode run --help`、`opencode models` |
| Antigravity（agy） | `agy --help`、`agy models` |
| GitHub Copilot CLI | `copilot --help`、`copilot help permissions` |
| Codex | `codex --help`、`codex exec --help`、`codex debug models` |
| Claude Code | `claude --help` |

CLI 更新後核對實際介面。旗標不支援時保留錯誤並交由 script 接手，不改用未核准的模型或執行模式。

## 內建工具交接

`native_required` 的模型選擇、派工與回報依 [SKILL.md](../SKILL.md#script-執行與內建工具交接) 執行。

## 對話續接

複用條件與隔離要求見 [SKILL.md](../SKILL.md#agent-與對話複用)。內建工具使用既有 agent 的續接功能，外部 CLI 使用原 session 的續接功能。參數查上表原生 help 或內建工具說明，明確指定識別碼，不用「最近一次」猜對話。

script 尚未提供 session 續接時，由主 agent 使用原生續接介面，保留任務、識別碼、實際模型、輸出與驗證紀錄。SKILL.md 的宿主 CLI 禁令、自動核准、可改範圍、併行限制與收件審查同樣適用。主 agent 在續接前後核對程序與檔案變動，包含忽略檔及授權沙盒。

script 的派工識別碼用於派工狀態接續，不等於模型對話的 session 識別碼，不以恢復派工狀態宣稱已複用對話。

## 狀態與半成品

script 的狀態保存原始任務、嘗試紀錄、錯誤與輸出位置。主 agent 接續前讀取紀錄、檢查程序及磁碟差異，補入已核對的經驗。續接失敗時，依 [工具失敗](../SKILL.md#5-工具失敗) 處理，不反覆嘗試失效 session。部分成果由主 agent 決定保留與接續方式，script 不自動刪除、stash 或 reset。

# AGENTS.md

在這個 repo 工作的 coding agent 都照這份規則做。`CLAUDE.md` 只引用本檔。專案介紹、安裝與測試指令在 [README.md](README.md)。

## 結構

```
.claude-plugin/plugin.json        ← plugin 名稱、描述、版本
.claude-plugin/marketplace.json   ← marketplace 宣告，只列 tstack 一個 plugin
hooks/                            ← hooks.json、提醒與指令防護腳本、它們的測試
skills/<skill>/                   ← skill 本體
```

每個 skill 一個資料夾：`SKILL.md` 是主檔，`references/` 放細節，`scripts/` 放可執行工具，`agents/` 放腳本的測試，`assets/` 放模板。

## Frontmatter

依 [Agent Skills 規範](https://agentskills.io/specification)，只用規範定義的欄位。

| 欄位 | 規定 |
|---|---|
| `name` | 必填，等於資料夾名，小寫英數與連字號 |
| `description` | 必填，英文觸發說明並嵌入中文觸發詞，少於 1024 字元。內含半形冒號加空格時用雙引號包住 |
| `metadata.version` | 必填，字串形式的語意化版本 |

`description` 用大寫的 RFC 2119 關鍵字寫出義務強度，寫進原有句子裡：

- `MUST`：使用者打出觸發詞，或這個 skill 是該類任務的預設做法。每個 description 至少一個。
- `SHOULD`：語意相關但需要判斷的情況。
- `MUST NOT`：要擋的誤用，或與其他 skill 的分界。
- 不用 `MAY`，也不要每句都是 `MUST`。

## 修改規則

- 新內容放進最合適的既有段落，不一律加在檔尾，不製造重複段落。加了規則後回頭檢查既有內容與示例是否仍一致。
- 條文只寫規則本身，不解釋原因，不寫成變更紀錄。規則改了就地更新原文。
- 主檔只留主幹流程，細節放 `references/`，並在主檔寫明哪一步要讀哪一份。
- 同一條規則同時出現在 `SKILL.md` 與 `scripts/` 的輸出文字時，兩邊一起改。
- 自製腳本的用法寫在腳本自己的 `--help`，skill 只指向它，不重複整份指令手冊。
- 不把特定裝置的路徑、主機名稱、安裝位置寫進 skill、規則或 hook。

## 引用規則

tstack 只支援整組安裝，skill 可以直接依賴其他 skill 存在，不寫「沒裝時怎麼辦」的替代條文。

- **每條規則只有一個主人。** 其他地方只放指向主人的連結，不重寫條文，也不寫摘要版。
- **多個 skill 共用的規則，主人是核心** `software-engineering-guidelines`。只屬於單一階段的規則，主人是那個階段的 skill。
- **引用只有三種方向：**

| 種類 | 誰指向誰 | 寫法 |
|---|---|---|
| 規則引用 | 任何 skill 指向規則的主人，通常是核心 | 相對連結到主人的標題 |
| 交接 | 階段 skill 指向流程的下一個 skill | 寫明交接條件與交出的內容 |
| 呼叫服務 | 階段 skill 指向 `agent-delegation` 或 `project-memory` | 呼叫方帶著自己的標準與內容去 |

- 核心不引用階段 skill 的條文，只在路由表點名它們。`agent-delegation` 與 `project-memory` 不引用階段 skill。
- 被引用的規則要有自己的標題，讓連結能指到它。改標題、改名或搬移時，同步更新所有指向它的連結。
- 什麼情況用哪個 skill，寫在核心的路由表。新增或調整 skill 時同步更新那張表。

## Hooks

- `reminders.py` 只提醒並指向 skill，不重複 skill 的規則。
- `guard.py` 只攔誤擋機率低、後果明確的指令，拒絕訊息必須寫出替代做法。新增攔截規則前先取得使用者同意。
- skill 的內容與流程不得依賴 hook，只裝 skill 的使用者沒有 hook。被 `guard.py` 攔下的做法，對應的 skill 也要寫明同一條規則。
- hook 發生任何錯誤都不輸出、以 0 結束，不擋住工作。

## 收尾檢查

- 動到 skill 的內容時，調升該 skill 的 `metadata.version`，並調升 `plugin.json` 的 `version`。只動 hook 或 repo 文件時調升 `plugin.json` 的 `version`。
- 新增、刪除或改變 skill 定位時，更新 README 的 Skills 表格；plugin 的收納範圍變了，同步更新 `plugin.json` 與 `marketplace.json` 的 description。
- 動過的 JSON 能解析，動過的 `SKILL.md` frontmatter 能通過 YAML parser，description 少於 1024 字元且含 `MUST`。
- 改了腳本或 hook，跑 README「開發」段列出的對應測試與 `claude plugin validate .`。
- 改變 skill 行為的修改，照 software-engineering-guidelines 的測試策略，在相同任務上比較新舊版本的實際表現。自動評審通過不等於使用者會接受。

## 變更節奏

一次交付一個 skill 的改動，讓使用者驗收後再繼續。大範圍新增或重寫前先提案。

## Active Issues

| ID | Task | Status |
|---|---|---|
| agent-delegation-opencode-startup-stall | opencode 有 4 次派工全程零輸出，紀錄停在啟動初期（`init`、`event connected`），沒有 provider 錯誤；同期另有 `database is locked`，疑似多條 opencode 搶同一個資料庫，未證實。遇到時用 `status` 的 `runtime` 判斷後 `cancel` | 待調查 |

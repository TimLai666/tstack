# tstack

一套給 coding agent 用的開發工作流，以 Claude Code plugin 的形式發佈。內容是 10 個 skill 加兩組 hook，涵蓋從釐清需求、設計、實作、除錯、測試、審查、資安掃描到交付的整段流程，以及派工給其他 agent 與跨 agent 共用的專案記憶。

## 安裝

Claude Code：

```
/plugin install tstack --marketplace TimLai666/tstack
```

較舊的版本分兩步：

```
/plugin marketplace add TimLai666/tstack
/plugin install tstack@tstack
```

其他支援 Agent Skills 的工具用下面的指令，並選擇安裝全部 skill（不含 hook）：

```
npx skills add TimLai666/tstack --all
```

tstack 是一個整體，只支援整組安裝。各個 skill 會直接引用彼此的內容，`software-engineering-guidelines` 是核心，負責指出什麼情況該用哪一個 skill，並保存所有 skill 共用的規則。只裝其中幾個會讓引用落空。

## Skills

| Skill | 適合什麼需求 |
|---|---|
| `software-engineering-guidelines` | 任何軟體改動的基本準則：先想清楚再寫、保持簡單、完整交付、測試策略、commit 訊息格式 |
| `eng-architect` | 架構決策、模組邊界、把計畫拆成可驗收的票 |
| `investigate` | 原因不明的錯誤、CI 紅燈、反覆出現的問題。附一份「看到什麼症狀先查什麼」的排查清單 |
| `test-and-fix` | 跑測試、找出失敗、修掉、驗證。規定什麼才算驗證過 |
| `diff-review` | 審查的單一入口。主對話自己寫的程式一律派給獨立的 reviewer 審，不自己審。開 PR、MR 或合併前審查程式 diff：需求範圍、邏輯與實作錯誤、相容性、可維護性、測試。資安相關的改動交給 `security-scan`，畫面的改動交給 `ui-review`，再把三邊的發現合併 |
| `security-scan` | 找安全漏洞並修補，可掃整個專案，也可只檢查一個 diff。每次掃描都抓當下最新的 CWE Top 25、OWASP 等清單，另附 17 類漏洞總表 |
| `ui-review` | 審查做出來的畫面：實際看渲染結果與互動，對照設計基準打分，找出套版感的問題 |
| `ship-it` | commit 之後的交付：push、開 PR 或 MR、合併。支援 GitHub 與 GitLab，合併前必須確認該 commit 的 CI 成功 |
| `agent-delegation` | 派工給 subagent 或其他 CLI（OpenCode、Antigravity、Copilot、Codex、Claude）的規範與派工腳本 |
| `project-memory` | 跨 agent 共用的記憶：專案裡花了很多力氣才找到的做法、這台機器的事實、遠端主機的事實 |

## Hooks

只有以 plugin 安裝時才有 hook。skill 本身不依賴 hook，用 `npx skills` 整組安裝時一樣能用。

**記憶與提醒**（`hooks/reminders.py`）：開新對話時（包含恢復、清空、壓縮後與分叉出來的對話）直接把這個專案的記憶與這台機器的事實放進對話，不用再多一次載入；記憶太長放不下時改列出各筆的 key。另外在幾個時間點提醒：開始工作前載入工程準則，commit 與 subagent 回報後記錄經驗。開 subagent 前如果這段對話還沒載入派工規範，會擋下那一次並要求先載入，每段對話只擋一次。

**指令防護**（`hooks/guard.py`）：攔下幾種反覆造成損害的指令，並在拒絕訊息裡給出替代做法。

| 攔下的指令 | 改用 |
|---|---|
| `git add -A`、`git add --all`、`git add .`、`git commit -a`（`git add --renormalize .` 除外） | `git add -- <路徑>` 逐一列出檔案 |
| 寫入 `git config --global` 或 `--system` | `git -c <名稱>=<值> <指令>` |
| `glab mr merge` 沒有帶 `--sha`，或沒有寫明 auto-merge 要開還是關 | 帶上 `--sha`。pipeline 已成功用 `--auto-merge=false` 立刻合併；還在跑且要全綠後合併用 `--auto-merge`；還沒有 pipeline 就先等 |
| 依名稱結束程序：`pkill`、`killall`、`taskkill /IM`、沒有 `-Id` 的 `Stop-Process` | 用 PID 結束自己啟動的那一個 |
| Windows 上的 `/tmp/` 路徑 | session 的暫存目錄或專案內的絕對路徑 |

需要關掉防護時，在啟動 Claude Code 的環境設定 `TSTACK_GUARD=off`。

## 記憶放在哪裡

都在本機的 `~/.tstack/` 底下，分三種：

| 記什麼 | 位置 | 何時載入 |
|---|---|---|
| 單一專案的經驗 | `projects/<專案>/learnings.jsonl` | 在那個專案開對話時 |
| 這台機器的事實，例如沒裝某個工具、某個路徑不能執行程式 | `machine/learnings.jsonl` | 在這台機器的每個專案開對話時 |
| 從這台連過去的遠端主機的事實 | `hosts/<主機名稱>/learnings.jsonl` | 開對話時只列出主機名稱，要到那台工作前才載入 |

機器與遠端主機的事實每筆最多 300 字，只寫條件與做法。遠端主機的事實存在本機，不會寫到遠端。

早期版本放在 `~/.mystack`。`project-memory` 的腳本每次執行都會先檢查這個舊資料夾，有的話把內容全部搬到 `~/.tstack`：新位置不存在時整個資料夾改名；兩邊都有時逐檔搬移，同一個專案兩邊都有紀錄就把新位置缺的那幾行補進去。搬不過去的檔案會留在原處並列出來，不會刪除。

## 開發

沒有建置流程。每次改完 skill 都跑一致性檢查，它會確認連結與錨點有效、引用方向沒有違反規則、每個 skill 都在核心的路由表裡、README 與設定檔同步：

```bash
python3 scripts/check_stack.py
```

改了腳本或 hook 之後另外跑對應的測試：

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

```bash
python3 -m unittest discover -s hooks -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/agent-delegation/agents -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/project-memory/agents -p 'test_*.py'
```

```bash
claude plugin validate .
```

修改 skill 的規則見 [AGENTS.md](AGENTS.md)。

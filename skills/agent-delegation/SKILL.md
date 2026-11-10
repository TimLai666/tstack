---
name: agent-delegation
description: >-
  This skill MUST be loaded when the user mentions subagent、分工、派工、
  antigravity、agy、opencode、copilot、codex or Claude Code Agent, before dispatching
  work even on small tasks, and when proposing
  changes to existing API names, signatures, usage or behavior（介面變更）.
  It MUST also be loaded before delivering specifications, articles, or reports（規格、文章、報告）for fresh-context review.
  It SHOULD be loaded for questions about who should code or which model to use.
  Existing API changes MUST follow the conditional consultation rule before
  implementation. New delegation MUST use scripts/dispatch.py and its task-local levels,
  and MUST NOT skip tools based on earlier turns. Main agents MUST define skeletons
  and expected results before implementation, protect tests, and avoid their own CLI.
  Dispatched workers MUST NOT apply this skill or delegate. Ordinary prompts MUST
  carry project lessons; workers MUST report lessons for verification and recording.
metadata:
  version: "3.0.0"
---

# Agent 派工規範

## Overview

主 agent 是強模型，負責寫骨架與每個格子的想要的結果、審查、驗證、提交。骨架鎖住範圍，弱模型照規格寫測試或填實作。一般派工的成本原則：依任務列的可用工具，照 OpenCode → Antigravity（agy）→ GitHub Copilot CLI → Codex → Claude 的順序派。測試、實作與雜事先交給 OpenCode 的免費模型，前端設計交給 agy 的 Gemini。Copilot 固定用 Auto，排在 agy 之後。方案取捨、技術選型與單一模組設計依序交給 agy 的 Opus、Codex 的 GPT-6 以上 sol、Claude 的 Opus。其他任務的模型與接手順序依下方決策表。任何 CLI 都能當主 agent，所以派工前先辨識自己是誰。原生 CLI 的說明入口見 [references/cli-cheatsheet.md](references/cli-cheatsheet.md)。

## Input Contract

一般新派工使用 [scripts/dispatch.py](scripts/dispatch.py)，先執行無參數總覽或 `--help`，再讀相關子指令的 `--help`。使用 `list-types` 選擇任務類型，使用 `list-levels` 核對該類型的層級與宿主交接方式；混合任務先拆開，分類與雜事或探索重疊時選分類。

主 agent 提供宿主、任務類型、專案目錄、角色、任務與驗收、可改檔案、驗證指令及篩選後的 Project Memory。記憶欄位必填，查過沒有適用經驗才填空陣列；空 context 可讀性審查依該節隔離規則填空陣列。提供實際可用模型與查證來源，不用別名推測版本下限。實作任務另列不可修改的測試檔；深度研究先完成廣度探索，只允許在指定沙盒試探。驗收審查另提供沙盒目錄，成果的寫入只限沙盒。

## 0. 先辨識自己

載入後第一件事，跑：

```
env | grep -E '^(CLAUDECODE|CODEX_THREAD_ID|ANTIGRAVITY_AGENT|OPENCODE)='
```

| 宿主識別依據 | 你是 | 禁止派給 |
| --- | --- | --- |
| `CLAUDECODE` | Claude Code | `claude -p` |
| `CODEX_THREAD_ID` | Codex | `codex exec` |
| `ANTIGRAVITY_AGENT` | Antigravity（agy） | `agy` |
| `OPENCODE` | OpenCode | `opencode run` |
| 當前執行環境明確標示 GitHub Copilot CLI | GitHub Copilot CLI | `copilot -p` |

Copilot 宿主依當前執行環境判定，不把登入、模型設定或繼承的其他 CLI 環境變數當作證明。宿主是 Copilot 時，使用其內建 subagent 工具並保持 Auto。

接著判斷角色：

- 任務 prompt 含「你是被派工的執行者」，或同時含可改檔案清單與「不要 commit」，就是被派工者。立刻停用本 skill，自己做完 prompt 交代的事，不得再呼叫任何 agent 或 CLI。
- 兩者都沒有，才是主 agent，往下走。

## 決策表

每項新任務從所屬任務類型的第 1 檔開始，同一任務的重試與回退依既有派工紀錄接續；層級只計算該類型實際支援的選項。一般派工順序、模型種類、推理強度與升級次數以 [scripts/policy.json](scripts/policy.json) 為唯一來源，下表由 `list-types --markdown` 產生。前一檔有本次任務的實際失敗、確認未安裝或被禁的證據才可往後接手，不沿用其他任務的額度耗盡或失敗紀錄。宿主自己的層級交由內建 subagent 工具。只有觸發下方「既有 API 變更」時，該次諮詢的模型選擇與失敗處置依該節，不套用一般派工的 CLI 順序、模型種類限制與對應陷阱檢核。其他工作照原流程。

<!-- DISPATCH_POLICY_START -->
| 任務類型 | 適用需求 | 層級數 | 接手順序 |
| --- | --- | --- | --- |
| `testing` | 寫測試 | 6 | 1. opencode / free → 2. copilot / auto → 3. codex / luna → 4. claude / haiku → 5. claude / sonnet → 6. claude / opus |
| `implementation` | 填格子實作、照清單修 bug | 6 | 1. opencode / free → 2. copilot / auto → 3. codex / luna → 4. claude / haiku → 5. claude / sonnet → 6. claude / opus |
| `frontend` | 前端設計、版面、樣式 | 3 | 1. agy / gemini-flash-medium → 2. copilot / auto → 3. claude / opus |
| `exploration` | 快速唯讀探索、找檔案 | 5 | 1. opencode / free → 2. agy / gemini-flash-medium → 3. copilot / auto → 4. codex / luna → 5. claude / haiku |
| `chores` | 機械性文件段落、證據整理、大量套版改寫 | 5 | 1. opencode / free → 2. agy / gemini-flash-medium → 3. copilot / auto → 4. codex / luna → 5. claude / haiku |
| `classification` | 分類、打標籤、編碼 | 3 | 1. copilot / auto → 2. codex / luna → 3. claude / haiku |
| `review` | 審 diff、找漏洞、對契約 | 3 | 1. agy / opus → 2. codex / sol → 3. claude / opus |
| `acceptance` | 驗收審查：對照原始需求實際操作成果 | 3 | 1. agy / opus → 2. codex / sol → 3. claude / opus |
| `research` | 深度研究的深度層 | 2 | 1. codex / sol → 2. claude / opus |
| `decision` | 方案取捨、技術選型、單一模組設計 | 3 | 1. agy / opus → 2. codex / sol → 3. claude / opus |
| `rules` | 寫 skill、prompt、規則與複雜架構 | 2 | 1. agy / opus → 2. claude / opus |
<!-- DISPATCH_POLICY_END -->

主 agent 自己做：寫骨架與想要的結果、審測試、派出去不划算的格子、讀 diff、跑測試、commit，以及統合深度研究的全部結果、做整體判斷。讀一個值、一份清單這類幾次工具呼叫就能完成的事也自己做，不派工。

### Script 執行與模型規則

- 新派工與層級接手一律透過 script，不自行重排工具、拼接派工指令或跳級。
- `dispatch` 在背景啟動外部 CLI，結果用 `status --dispatch-id <ID> --wait <秒數>` 取得。`cli_failed`、`awaiting_review`、`native_required` 都交回主 agent 判斷與審查，不把 CLI 成功當成驗收通過。
- 同一個 CLI 同時最多三條，內建 subagent 也計入。不用宿主自己的 CLI 指令派工，改用內建 subagent 工具。
- 模型種類、推理強度、升級條件與各結果的處理步驟寫在 [references/script-execution.md](references/script-execution.md)。這次對話第一次派工前完整讀過；之後遇到沒處理過的 `status` 結果、要選模型或調整推理強度時，重讀對應段落。

### 既有 API 變更

只有準備變更既有 API，或函數、變數、結構體、Enum 等程式元素的命名、結構、用法或行為時，才啟動本節。不因任務涉及 API、一般設計、審查或派工就啟動。純內部實作調整若保持上述項目不變，或單純新增且不改變既有名稱、結構、用法或行為，照原流程。

條件成立時，在修改受影響的骨架、測試或實作前，完整讀 [references/api-change-consultation.md](references/api-change-consultation.md)，照它完成獨立模型諮詢、修正初案與使用者確認，再接回實作。

### 骨架與格子

派實作前，主 agent 先照核心的 [Skeleton First](../software-engineering-guidelines/SKILL.md#skeleton-first) 寫好骨架，每個格子都有簽名與想要的結果清單。

邏輯短到交代與審查比直接寫還費工，或說不清楚要改哪裡的格子，主 agent 自己寫。其餘格子照下列順序派：

1. 派測試 agent，照想要的結果寫測試，不寫實作。
2. 主 agent 審測試：逐條對照想要的結果，並在空格子上跑一次。有測試通過的退回重寫。
3. 派另一個實作 agent 填格子，填到測試通過，不得修改測試檔。認為測試錯就停下回報，由主 agent 裁決。
4. 主 agent 照「收件審查」驗收。

沒有測試環境或畫面類的格子，測試換成可執行的驗證步驟，由測試 agent 寫成指令或檢查清單。

## 派工流程

每一步的細則在 [references/dispatch-flow.md](references/dispatch-flow.md)，到那一步才讀對應的段落。

1. **派工前**：帶入篩選過的專案記憶、確認沒有別人的半成品與同檔寫入、確認該 CLI 沒有超過三條，並判斷複用既有對話或新建。讀「派工前」與「Agent 與對話複用」。
2. **發起**：用 script 提交。prompt 的七項由 script 依欄位產生，欄位怎麼填讀「派工 prompt 必備七項」。派審查之前讀 [references/review-isolation.md](references/review-isolation.md)。
3. **派工中**：背景派工結束時會通知，等通知，不排定時喚醒或輪詢。中斷、重派與半成品的處理讀「派工中」。
4. **收件審查**：照下方清單親自做。
5. **失敗**：script 回 `cli_failed`、指令找不到、額度耗盡或逾時時，讀「工具失敗」與「CLI 未安裝」，自行接續下一層，不問使用者要不要重試。
6. **回報**：照下方格式。

規格、文章或報告交付前，MUST 依 [references/review-isolation.md](references/review-isolation.md) 的「空 context 可讀性審查」派一個未參與撰寫的 subagent 檢查。

### 收件審查

主 agent 親自做，不派另一個 agent 代審。規格、文章或報告交付前，另依「空 context 可讀性審查」檢查成品能否獨立理解。

- [ ] 讀完整 diff：`git diff`，不是只看 subagent 摘要。
- [ ] 回報裡的每個數字、測試通過數、檔案數，都對回實際輸出或檔案。
- [ ] 核對覆蓋範圍。實際處理數少於應處理數，或有來源沒取得時，補派或在成果裡標明缺口，不當成完整結果彙整。
- [ ] 自己跑一次驗證指令，貼實際輸出。subagent 說「測試通過」不算證據。
- [ ] 比對可改檔案清單，多改的檔案一律退回。實作 agent 的 diff 碰到測試檔也退回。
- [ ] 全部格子完成後跑完整使用流程驗收。
- [ ] 才決定採用、退修或丟棄。
- [ ] 交給使用者的是主 agent 整合後的完整內容，不是摘要，也不是各 subagent 回報的轉貼。
- [ ] 不論成果採用或退修，都核對 subagent 回報的試錯與探索經驗，連同主 agent 自己的發現，判斷能否避免下次重複耗費時間與 token。依 project-memory 的記錄標準篩選，不把推測、流水帳或未解問題當成已驗證教訓。
- [ ] 對符合條件的經驗，在原專案目錄依 project-memory 的工具先搜尋去重，再新增或更新，無須逐筆詢問使用者。舊記憶須查證確實失效後才更新原 key，保留仍有效的適用條件。寫入後讀回確認，不宣稱未完成的記錄已保存。

### 回報

每次回報獨立一段列出宿主與每次派工：

```
宿主：Claude Code
工具與模型：agy / <實際 flash 模型名> / --mode accept-edits --dangerously-skip-permissions
工具與模型：opencode / <實際免費模型名> / --agent build --auto
```

每次派工註明實際工具、模型、旗標、新建或複用、agent 或 session 識別碼及隔離對象。回退附本次任務的失敗或未安裝證據。只有取得工具的快取用量證據時，才回報實際命中快取。新建時簡述無法複用的原因。沒派工就寫「工具與模型：無」。每次交接與收件依 script 輸出提醒執行：核對教訓與經驗，依 project-memory 流程搜尋去重、記錄並讀回確認。

## 陷阱

每次回報前逐列核對 [references/pitfalls.md](references/pitfalls.md)。

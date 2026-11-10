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
  version: "2.27.1"
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
4. 主 agent 照第 4 節收件審查。

沒有測試環境或畫面類的格子，測試換成可執行的驗證步驟，由測試 agent 寫成指令或檢查清單。

## 派工流程

### 1. 派工前

空 context 可讀性審查的輸入與重派依該節隔離規則，其餘檢查照常執行。

- [ ] 主 agent 依照 `project-memory` skill 載入目前專案的記憶，按這次 subagent 的任務搜尋可能相關的經驗。已載入的內容可沿用，但任務範圍改變時重新篩選。把適用條件、踩坑重點、已驗證做法與來源帶進 prompt，不只給 key 或要求 subagent 自己找，也不整份貼上無關記憶。舊經驗與現況不符時依 project-memory 的失效查證規則處理。

- [ ] 跑 `git status --short`。有未提交變更時逐檔確認是自己這輪的、還是別的 agent 的半成品。是半成品就先處理完再派。
- [ ] 確認這組檔案目前沒有別的會寫檔的 agent 在跑。同一組檔案同時只能有一個會寫檔的 agent。
- [ ] 確認要用的 CLI 目前跑不到三條，滿了就等其中一條結束。
- [ ] 並行派工前，替每一條劃定可改檔案與輸出目錄，彼此不重疊，也不與主 agent 自己會清理或覆寫的目錄重疊。
- [ ] 需要瀏覽器的並行派工各用自己的瀏覽器實例，不共用同一個。
- [ ] 無人值守的排程或背景流程裡，先定出並行條數與每條派工的時間或工具呼叫上限，寫進 prompt。
- [ ] 透過 script 查詢任務類型及層級，核對本任務可能用到的外部 CLI 安裝狀態。找不到指令時先依「CLI 未安裝」查證，再依下節選擇複用或新建，提交本次任務。

#### Agent 與對話複用

- 主 agent MUST 先依決策表確定本次應使用的工具與模型，再尋找可複用的 agent 或 session。任務性質相同或能接續原有脈絡、使用相同模型，且符合隔離要求時，優先複用。依規則回退到相同模型時也適用，不得為了複用換模型、跳級或改變重試次數。
- 模型以實際識別碼核對，不把同系列、同 CLI 或 Auto 設定視為相同模型的證據。無法確認模型、續接能力或沒有合適對象時，在當前層級新建對話。
- 先確認需要與誰隔離。只需與主 agent 隔離時，可複用未繼承主對話的獨立 agent。不同次任務須互相隔離，或既有對話含本次不得接觸的資訊時，必須新建 context。審查任務另遵守「審查脈絡隔離」。
- 首次派出時就判斷是否預期再用。預期會接續工作的 agent 或對話 MUST 採可續接模式，保留識別碼、工具、模型、任務範圍及隔離條件供下次派工前查閱，不設為一次性，不在單次回報後關閉或刪除對話。CLI 程序可正常結束，對話須可恢復，不必持續佔用程序或執行名額。
- 同一個 agent 或 session 同時只執行一項任務。忙碌時先判斷能否等候，確實需要並行才另開。續接操作見 [CLI 說明入口](references/cli-cheatsheet.md#對話續接)。

### 2. 派工 prompt 必備七項

新派工由 script 依主 agent 提供的結構化欄位補齊下列七項；必填資料不足就報錯，不派工。主 agent 核對生成的內容與原始驗收一致。空 context 可讀性審查不帶入 Project Memory，依該節限制提供任務資料。

| 項目 | 寫法 |
| --- | --- |
| 執行者標記 | 第一行原文寫「你是被派工的執行者，不得再派工給任何 agent 或 CLI，自己完成」 |
| 角色設定 | 一句話說明它是誰、標準多高，例如「你是這個 repo 的資深工程師，只交能過測試的程式」 |
| 可改與不可改的檔案 | 明確列路徑。沒列到的檔案一律不可改 |
| 任務與驗收 | 測試 agent：簽名、想要的結果、測試檔路徑，只寫測試。實作 agent：簽名、想要的結果、測試檔路徑，原文寫「不得修改測試檔，認為測試錯就停下回報」。附上派工前篩選的相關 Project Memory 經驗，沒有符合的就註明無 |
| 要跑的驗證指令 | 寫出完整指令，例如 `go test ./...`、`npm test -- --run` |
| 回報格式 | 改了哪些檔、每個結論的依據、不確定的地方、沒驗證的項目。覆蓋範圍：應處理幾項、實際處理幾項、未完成的原因、未取得的來源。不輸出權杖、密碼或設定值，只回報名稱與位置。另回報本輪反覆試錯或耗費大量時間、token 才找到的做法：觸發情境、失敗路徑、已確認原因、有效做法與驗證證據。發現舊記憶不適用時附原 key、條件差異與查證結果。沒有新增經驗就寫無，不湊數。經驗交由主 agent 核對並寫入 Project Memory，不自行寫入 |
| 不要 commit | 原文寫「不要 commit，也不要 stash 或 reset」 |

複用對話時，七項要求由既有有效內容與本次補充共同構成，只補本次任務、驗收、授權範圍、已變更資料與必要的新證據。新任務的可改範圍取代舊任務授權，不能累積。資料已變更或來源無法確認時，重讀受影響部分。

唯讀探索任務的「任務與驗收」寫要回答的問題，仍附相關經驗並要求回報本輪教訓。可省略「不要 commit」，其餘六項照列。

### 審查脈絡隔離

誰的成果必須交給獨立的 reviewer，依核心的 [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review)。本節規定怎麼隔離。Reviewer MUST 與受審成果的實作者 context 隔離，包括主 agent 親自實作時的主對話。不得把實作者的 agent 或 session 改名、換角色或要求忽略前文後拿來審查，也不得透過對話繼承或轉貼實作討論帶入該脈絡。要求互相獨立的角色，即使分不同時間執行也不得共用 context。此規則同時適用於內建工具與外部 CLI。

一般審查提供需求、驗收條件、程式碼、diff 與可核對的驗證證據。既有 reviewer 只有在未帶入受審成果的實作脈絡，且本次審查不要求與前次審查隔離時才能複用。空 context 可讀性審查另依下節限制輸入與複查方式。

#### 空 context 可讀性審查

規格、文章或報告完成、準備交付前，MUST 派一個未參與撰寫的 subagent，檢查目標讀者能否在沒有本次對話的情況下理解成品。主 agent 親自撰寫的成品也適用；程式實作與一般對話答覆不因此新增審查。

- 依 `review` 類型派工，除上述角色隔離外，還須隔離本成品的修改與前次審查脈絡。只處理過不影響本次判讀的其他成品的 reviewer 可依複用條件沿用。新建時關閉對話繼承，不能隔離時依工具失敗流程接手。
- prompt 只交代目標讀者、閱讀目的、成品及讀者實際可取得的資料，並保留派工的角色、唯讀範圍、驗收與回報要求。不得提供主對話、寫作計畫、修改理由、預期解讀或前次審查答案；`project_memory` 填 `[]`，相關經驗由主 agent 自行核對，不交給審查者。
- 提供規格、文章或報告的完整正文與隨附資料，包含讀者實際能取得的引用文件與附件；不要求讀者具備超出目標讀者設定的知識。
- 審查者先用自己的話說明成品主旨，規格另說明要求的行為與驗收條件，報告另說明主要結論與依據，再逐項指出無法理解的位置、可能的誤解、缺少的資訊與最小修正建議，附段落、頁碼或檔案行號。不得修改任何檔案，不自行腦補缺失資訊；沒有發現問題就明說。
- 主 agent 對照成品核對意見，修正確實依賴隱藏脈絡的部分。優先改善結構、命名或刪除無關內容，必要時才補說明；可讀性審查不取代事實查證、測試或正確性審查。
- 修正後以更新成品重新發起派工，用新的空 context 複查，不沿用前次審查者或帶入前次回報。工具失敗依原流程接續，但接手 prompt 只保留啟動或執行失敗證據，不帶入成品解讀或審查意見。交付時如實區分已通過、仍有缺口與工具受阻。

### 3. 派工中

- [ ] 背景 agent 與背景指令結束時會通知主 agent。等通知，不排定時喚醒或輪詢。
- [ ] 背景 agent 被中斷時先看磁碟：`git status --short` 加 `git diff --stat`，判斷做到哪裡。
- [ ] 需要重派時，原 prompt 從記錄檔取回，不憑記憶重寫。Claude Code 的 subagent 在 `head -1 ~/.claude/projects/<專案>/<session>/subagents/agent-<id>.jsonl`，其他 CLI 見速查表的續接欄。
- [ ] 重派前把前一位執行者已驗證的相關教訓補進原 prompt，保留證據與不確定處，再交給接手者。
- [ ] 重派前決定半成品去留：保留並告知新 agent，或 `git checkout -- <檔案>` 清掉。

### 4. 收件審查

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

### 5. 工具失敗

一般派工的授權包含依 script 規則重試與改派。主 agent MUST 自行處理工具失敗並接續，MUST NOT 因單一工具失敗、額度耗盡、模型不可用、未登入或內建工具不可用，就詢問使用者是否重試、改派或繼續。接手順序與複用條件依決策表及「Agent 與對話複用」執行。

script 記錄每次失敗的原始輸出與實際旗標。`native_required` 由主 agent 使用指定的內建工具派工，失敗時帶實際錯誤接續。`cli_failed` 與 `awaiting_review` 都是主 agent 的判斷點，不是使用者的確認點：主 agent 自行檢查程序、磁碟、半成品與驗證結果，再帶原派工識別碼及實際證據依 script 接續，遵守同級重試與不可跳級的限制。無法確認程序已停止或半成品可安全接續時，先排除阻礙，不盲目重派。

該類型的選項全部失敗，或接續確實需要使用者登入、授予權限、額外付費、擴大任務範圍或決定可能遺失成果的處置時，才停下來請使用者決定。單一工具需要這些操作，但後續仍有已授權且可安全接續的選項時，先依 script 改派，不要求使用者修復該工具。既有 API 變更的指定模型諮詢沿用該節的失敗處置。

#### CLI 未安裝

- 主 agent MUST 在因未安裝而跳過 CLI 前查證安裝狀態，不得只憑一次 `command not found`、`which` 無結果或 script 的啟動錯誤判定未安裝。先核對目前執行環境與使用者正常使用的 shell 的指令解析及 PATH，再依既有設定、套件管理器安裝紀錄與該工具的標準安裝位置確認。只查相關位置，不掃描整個磁碟。
- 找到候選執行檔時，以明確路徑執行版本或 help 查詢，確認是否為該 CLI。已安裝但不在 PATH、權限不足、啟動器損壞或缺少執行環境，均記為對應的啟動問題，不記為未安裝。查證受阻時如實記為無法確認，再依已有錯誤證據處理，不宣稱未安裝。
- 確認未安裝後，保留查證命令與結果，依決策表跳過該外部 CLI 並接續可用選項，不自行安裝、重裝或使用會自動下載工具的啟動方式。除非使用者另有明確安裝指示，不為完成派工安裝 CLI。確認未安裝後，接續時加上 `--not-installed`，並把查證指令與結果寫進 `--failure-reason`。script 會記下這份查證，之後的派工在 PATH 沒變、指令仍找不到且未滿 7 天時自動跳過該工具，並在 `attempts` 附上當時的證據；這三個條件任一不成立就照常啟動並重新查證。無法確認是否安裝時不加這個參數。宿主內建工具的可用性另行判斷，不因同名外部 CLI 未安裝而跳過。

| 症狀 | 回報寫法 |
| --- | --- |
| CLI 未安裝或啟動失敗 | 貼查證命令、結果與判定，區分未安裝、PATH 問題及其他啟動錯誤 |
| 模型不存在或需升級 CLI | 貼錯誤原文與 `agy models`／`opencode models`／`codex debug models` 輸出 |
| 權限被拒、未登入 | 貼錯誤原文，說明需要哪個權限或登入指令 |
| 逾時 | 貼逾時設定與已完成部分 |
| 額度耗盡（rate limit、quota、usage limit） | 貼錯誤原文 |

### 6. 回報

每次回報獨立一段列出宿主與每次派工：

```
宿主：Claude Code
工具與模型：agy / <實際 flash 模型名> / --mode accept-edits --dangerously-skip-permissions
工具與模型：opencode / <實際免費模型名> / --agent build --auto
```

每次派工註明實際工具、模型、旗標、新建或複用、agent 或 session 識別碼及隔離對象。回退附本次任務的失敗或未安裝證據。只有取得工具的快取用量證據時，才回報實際命中快取。新建時簡述無法複用的原因。沒派工就寫「工具與模型：無」。每次交接與收件依 script 輸出提醒執行：核對教訓與經驗，依 project-memory 流程搜尋去重、記錄並讀回確認。

## 陷阱

每次回報前逐列核對 [references/pitfalls.md](references/pitfalls.md)。

# Script 執行、模型規則與內建工具交接

發起派工、處理 `status` 回傳的結果，或決定模型與推理強度時照本檔執行。主檔指的是 [SKILL.md](../SKILL.md)。

- 主 agent 必須透過 script 發起新派工與處理層級接手，不自行重排工具或拼接派工指令。符合「Agent 與對話複用」時，依該節續接原 agent 或 session。操作與參數查詢使用 CLI 的總覽及子指令 `--help`；原生工具說明入口見 [CLI 速查表](cli-cheatsheet.md)。
- 會啟動外部 CLI 的派工在背景執行，`dispatch` 輸出 `started` 後就結束。主 agent 用 `status --dispatch-id <ID> --wait <秒數>` 取得結果，秒數不超過自己指令工具的執行上限，結果仍是 `running` 就再查一次。宿主能在背景執行指令並在結束時通知，就可用它跑較長的 `status --wait`。`--timeout` 是單次執行外部 CLI 的上限，依任務需要設定，不為了配合自己指令工具的上限而縮短。
- `status` 的 `runtime` 顯示工作程序很久沒有新輸出，主 agent 判斷它已經卡住時，用 `cancel` 停止，再依 `awaiting_review` 審查。結果為 `not_started` 表示此層還沒有啟動執行者，解除佔用後用 `--outcome dispatch-failed` 在同一層重來。
- 外部 CLI 失敗而且檔案沒有變動時，結果為 `cli_failed`。script 不解讀錯誤內容，主 agent 讀 attempts 最後一筆的原始輸出判斷原因；指令無法啟動（`launch_error`）先依「CLI 未安裝」查證。判定這一層無法執行後，帶錯誤原文與判斷用 `--outcome dispatch-failed` 接下一層。正常回報、部分改檔與逾時先交回主 agent 審查，不把 CLI 成功當成驗收通過。
- 結果為 `native_required` 時，主 agent 使用輸出指定的內建工具與合規模型，先依複用條件選擇既有 agent，再提供本次完整任務要求。禁止改用宿主自己的 CLI。內建 subagent 完成後，照 `awaiting_review` 的方式審查並用 `--outcome` 回報。內建工具不可用或派工失敗時，帶原派工識別碼、實際錯誤與下一層級接續；不可跳級。
- 結果為 `awaiting_review` 時，主 agent 讀 diff、核對範圍並親自驗證。回報已完成驗收、派工失敗或驗證失敗時，依 CLI 的條件接續。寫程式同級連續兩次驗證失敗才升級，不能把成果不合格冒充為未派出。
- 每次接續讀取原派工狀態，保留原 prompt、失敗證據與補充教訓。逾時、中斷或取消後，先由主 agent 確認程序及半成品，再依「工具失敗」的接續與停止條件處理。
- 狀態與原始輸出存於專案外的使用者狀態目錄，由 script 接續與主 agent 審查時讀取；不在使用者專案根目錄新增協調檔。script 只替自己啟動的外部 CLI 計算名額與同檔寫入。交給宿主內建 subagent 的派工不佔名額也不鎖檔，主 agent 自己把它計入每個 CLI 三條的上限與同檔檢查，其他 agent 與未納管寫入也由主 agent 查證。
- 每次外部 CLI 結束，script 先停止其工作程序群，再檢查所有專案檔案（含忽略檔）與授權沙盒。掃描無法完成或有變動就先審查。需要持續執行的服務由主 agent 管理。

- 外部 CLI 派工一律明確指定自動核准：OpenCode 加 `--auto`，Copilot 加 `--allow-all-tools`，Codex 加 `--approve-for-me`，agy 加 `--mode accept-edits --dangerously-skip-permissions`，Claude Code 加 `--permission-mode auto`，Claude Code 不改用 bypass。Claude Code 與 agy 從目標專案目錄啟動。
- 自動核准不擴大任務可改檔案清單。表中的「唯讀」只表示 prompt 必須明寫「不得修改任何檔案」；探索、審查與實作沿用相同執行模式，不另設 plan、read-only 沙盒或唯讀工具清單，也不選唯讀專用 agent。宿主內建 subagent 不套用外部 CLI 旗標，可改範圍同樣寫在 prompt。

- 表中只寫模型種類。script 輪到 OpenCode、agy 或 Codex 時，自行以 `opencode models`、`agy models` 或 `codex debug models` 查實際可用模型。agy 與 Codex 挑該種類中版本最新的；OpenCode 的免費模型有 `opencode/big-pickle` 就用它，沒有時取 `opencode/` 開頭的清單裡排序最後的一個。
- Copilot 依本專案的免費版使用方式固定設 `--model auto`，不指定具體模型、推理強度或付費替代方案。`--allow-all-tools` 允許自動執行包含改檔在內的工具，`--trust-folder` 僅信任本次 prompt 模式的工作目錄設定。prompt 的可改範圍不變。Copilot 只用於決策表中明列 Auto 的任務，手動指定模型的種類限制不套用 Auto 的內部選擇，但 Auto 不作為 Fable、Opus 或 Astra 的指定模型諮詢。
- opencode 只能用免費模型：`opencode models | grep opencode/` 查得到才算。
- Codex 照表主動派。Review、深度研究與決策只用 GPT-6 以上、名稱含 sol 的模型。名稱含 luna 的模型只用於寫測試、填格子實作、照清單修 bug、快速唯讀探索、雜事與分類。
- 深度研究分三層：
  1. 廣度層：照「快速唯讀探索」那列派（OpenCode、Gemini Flash、Copilot Auto、luna、Haiku），每條負責一個範圍，掃描並回報發現與線索，附出處。回報當成線索，不當成事實。
  2. 深度層：主 agent 從線索挑出值得深挖的項目，每個項目依深度研究那列先派 sol，失敗後才派 Opus，一次只專研一件事，prompt 只放那一件。回報系統結構、可行做法與每個結論的依據（檔案路徑、指令輸出、文件出處）。
  3. 統合層：主 agent 合併廣度與深度的全部結果，核對關鍵依據、前後對照、做出整體判斷，決定採用哪個做法並親自執行。執行者的結論不直接當成定論。
  廣度層沒挑出值得深挖的項目時，不派深度研究。
- 深度研究的 agent 可實際試探系統，但可改檔案只列暫存目錄或沙盒，專案檔一律不可改。試探造成的副作用（建立的檔案、啟動的程序、改過的設定）一併寫進回報，由主 agent 決定保留或清掉。
- 非免費模型的 effort 預設 `medium`，主 agent 判斷任務需要時才調高，最高 `xhigh`。agy 的 Gemini 選模型名結尾是 `-medium` 的版本，agy 的 Claude 不加 `--effort`，思考強度由模型名稱決定。Agent 工具沒有 effort 參數，不用設。
- Haiku 與 Sonnet 只用 5.5 以上版本，所以 agy 的 Sonnet 4.6 不派。
- Haiku 用在唯讀探索、雜事、分類與簡單的寫程式任務。
- 任務同時符合分類與雜事或探索時，照分類那一列派。
- 輪到 Claude 時，Sonnet 用在 Haiku 寫不出來的寫程式任務。
- Opus 只用在前端設計、決策、寫規則、複雜架構、review、深度研究，以及 Sonnet 也沒過驗證的寫程式格子。派工順序依決策表，接手寫程式格子時 `claude -p` 改用 `--effort low`。
- 寫程式那一列，同一個格子在同一級連續兩次沒過驗證才往下一級，claude 那欄依 Haiku、Sonnet、Opus 的順序升級。
- 同一個 CLI 同時最多跑三條，Copilot 也計入，Claude Code 的 Agent 工具也算 claude。
- 不用宿主自己的 CLI 指令派工（`claude -p`、`codex exec` 等），改用宿主內建的 subagent 工具。同一個模型不同 CLI 可以。
- 一般派工的唯一例外：主 agent 判斷很難的寫程式格子，若這次任務裡 opencode 已在同類型的格子交出不完整或沒過驗證的結果，可以跳過 OpenCode，從 Copilot Auto 派起，失敗後再派 luna，其餘往下升級的規則不變。

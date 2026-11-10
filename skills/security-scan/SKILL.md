---
name: security-scan
description: "Find security vulnerabilities in code the user owns, then fix and verify them: a whole project, or one diff handed over by diff-review. This skill MUST be used when the user asks for a security scan, audit or hardening, and for the security part of a diff review. It SHOULD be used before a first public release and after adding authentication, payment, file upload or anything that takes outside input. It MUST fetch the current CWE Top 25, OWASP and related lists at scan time and MUST NOT rely on remembered editions. It MUST NOT be used against systems or code the user does not own or is not authorized to test. Triggers on: 資安掃描、資安審查、漏洞掃描、找漏洞、補漏洞、security scan、security audit"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
  - WebFetch
  - WebSearch
metadata:
  version: "1.5.1"
---

# 資安掃描

## Overview

替使用者自己開發的程式找出安全漏洞並修補。檢查項目有兩個來源：掃描當下抓到的最新公開清單（CWE Top 25、OWASP 各清單等），以及這個 skill 附的[漏洞總表](references/vulnerability-catalog.md)。每個發現都要有程式碼位置與可重現的觸發方式，修完再驗證一次。

有兩種模式：

| 模式 | 什麼時候用 | 範圍 |
|---|---|---|
| 全專案 | 使用者要求掃描或健檢 | 整個專案或指定的目錄 |
| diff | **diff-review** 交接過來，或使用者要檢查某個 diff、PR、MR 的資安 | 這個 diff，加上它的輸入與輸出會經過的既有程式 |

這個 skill 只管漏洞。邏輯錯誤、實作缺陷、效能與可維護性由 **diff-review** 審查，原因不明的錯誤用 **investigate**。

## Input Contract

| 項目 | 取得方式 |
|---|---|
| 模式 | diff-review 交接，或使用者指名 diff、PR、MR 時用 diff 模式，其餘用全專案模式 |
| 掃描範圍 | 全專案模式：使用者指定的目錄、服務或功能，沒指定就是整個專案。diff 模式：指定的 diff 與比較基準，不明確時依 git 狀態與 PR、MR 的目標分支判斷 |
| 授權 | 程式是使用者自己的，或使用者說明有權測試。無法確認時先問，不開始掃描 |
| 要不要直接修 | 使用者說「補」「修」就修；只說「掃」「檢查」就先交報告，修補等確認。diff 模式預設只回報 |
| 可用的測試環境 | 從專案設定與文件找本機啟動方式。沒有可隔離的環境時，動態驗證改成靜態證據並在報告標明 |

## Workflow

### 1. 確認範圍與邊界

- 讀專案的規則檔、架構文件與既有的安全相關紀錄。用 **project-memory** 載入本專案的記憶。
- 只測使用者擁有或獲授權的程式與環境。重現漏洞只在本機或測試環境進行，不對正式環境與第三方服務送攻擊請求，不讀取、不帶出真實使用者的資料。
- 掃描期間不改動程式。修補在步驟 6 進行。
- 這段對話寫過或改過掃描範圍內的程式時，步驟 3 到 5 依核心的 [Independent Review](../software-engineering-guidelines/SKILL.md#independent-review) 派給獨立的 reviewer 做，主對話只核對發現。修補之後的複查也一樣。被派來的 reviewer 自己完成掃描，不再派工。

### 2. 抓最新清單

照 [references/list-sources.md](references/list-sources.md) 的規則，從入口頁抓出適用清單的最新版，記下每份清單的名稱、版本、網址與抓取日期。抓不到的清單依該檔的規則處理並記錄。

### 3. 盤點攻擊面

列出下面幾項，每項附檔案位置。這份盤點決定後面要檢查哪些地方。

- 入口：HTTP 路由、GraphQL 操作、RPC、WebSocket、CLI 參數、排程、訊息佇列消費者、webhook、檔案匯入、深層連結。
- 信任邊界：哪些輸入來自匿名使用者、已登入使用者、其他租戶、第三方服務、模型輸出。
- 敏感資產：帳密與金鑰、個資、金流、管理功能、檔案系統、對外發出的請求、可執行指令的地方。
- 身分驗證與授權的實作位置，以及哪些入口沒有經過它。
- 技術組成：語言、框架、資料庫、依賴套件與 lockfile、容器與部署設定、CI/CD 設定。

### 4. 掃描

三條線都要做，結果合併後去重。

**4a 工具掃描。** 照 [references/scan-tools.md](references/scan-tools.md) 做：依專案實際有的檔案找出適用的工具，逐一確認能不能用，能用的都跑。沒有安裝的不自行安裝，列進報告的建議。工具的輸出是線索，每一筆都要回到程式碼確認。

**4b 清單對照。** 步驟 2 抓到的每一項都要有結論：有發現、已檢查無發現（寫出看了哪些位置）、或不適用（寫出依據）。

**4c 總表對照。** 站在攻擊者那一邊看：假設每個輸入都由想突破系統的人控制，主動找出能繞過驗證、越權或濫用流程的路徑，不只確認防護存在。逐節走過[漏洞總表](references/vulnerability-catalog.md)。對步驟 3 的每個入口，從輸入一路追到它被使用的地方（查詢、指令、檔案、回應、對外請求），確認途中有沒有該節的防護。不要只搜尋危險函式名稱：授權缺失、邏輯漏洞與競態都搜尋不到，要讀流程。

範圍大時可以依節或依模組分派 subagent，照 **agent-delegation** 派工。每條派工劃定互不重疊的檔案範圍，prompt 寫明不得修改檔案、不得輸出秘密的值。回報要附檔案行號與判斷依據，由主 agent 回到程式碼核對後才採用。

### 5. 確認與分級

每個候選發現先確認再列入：

1. 指出輸入從哪裡進來、經過哪些程式、在哪一行造成問題。
2. 說明攻擊者需要什麼條件（匿名、已登入、特定角色、需要受害者互動）。
3. 能安全重現的，在本機或測試環境重現並保留請求與結果。不能重現的，寫出缺少的條件，放進「待確認」。

找不到可行的觸發路徑就不算漏洞，可以放進「強化建議」。

等級用核心 [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity) 的 P0 到 P3。資安發現的判定標準：

| 等級 | 判定 |
|---|---|
| P0 | 不需登入或只需一般帳號，就能執行任意程式、取得或竄改大量資料、接管他人帳號或提升到管理員 |
| P1 | 能存取或修改其他使用者的資料、繞過付款或關鍵流程，或需要的條件容易達成 |
| P2 | 需要特定條件或受害者互動，影響限於單一使用者或有限的資料 |
| P3 | 影響很小，或需要多個不容易同時成立的條件 |

依賴套件的漏洞另外確認兩件事：專案有沒有實際呼叫到受影響的功能，以及該 CVE 是否在 CISA KEV 清單上。在清單上的往上調一級。

### 6. 修補

由 P0 到 P3 依序處理。修補照 **software-engineering-guidelines** 進行：

- 修根因，並搜尋同一種寫法的其他位置一起修。
- 優先用框架或函式庫提供的防護，不自己寫跳脫、加密或驗證。
- 每個修補都要有核心 [Regression Tests](../software-engineering-guidelines/SKILL.md#regression-tests) 規定的回歸測試。
- 發現外洩的秘密時，從程式移除不算修好。請使用者到發行該秘密的服務撤銷並重新產生，歷史紀錄的清理另外確認，不擅自改寫 git 歷史。
- 會改變既有行為、介面或資料的修補，先說明影響並取得確認。

### 7. 驗證與報告

- 重跑步驟 5 的重現步驟，確認已擋下。
- 重跑步驟 4a 的工具與專案的完整測試，確認沒有引入新問題。
- 依 Output Contract 交報告。

### diff 模式

步驟 1 到 7 照走，差別如下：

- **範圍（步驟 3）**：只盤點 diff 新增或改動的入口、資料流、設定與依賴。每一條都要追出 diff 之外：輸入從哪段既有程式進來，改過的值又流到哪裡。改動拿掉或繞過既有防護時（驗證、授權、跳脫、限速），列為候選發現。
- **清單（步驟 2）**：這次對話已經抓過的清單直接沿用。還沒抓過時，抓 CWE Top 25、OWASP Top 10，以及 diff 碰到的技術對應的清單。
- **掃描（步驟 4）**：依賴或 lockfile 有變動時，稽核新增與升降版的套件。diff 內新增的字串逐一檢查有沒有秘密。總表只對照 diff 碰到的那幾節，其餘各節不用列。
- **修補（步驟 6）**：預設不修，把發現交回呼叫方。使用者或呼叫方要求修時才修。
- **角度**：由 diff-review 交接的資安審查就是對抗式審查的資安部分。任務寫明要以攻擊者的角度進行時，對 diff 新增或改動的每個入口都實際設想一條攻擊路徑，再判斷它走不走得通。
- **回報**：只交 Output Contract 的第 1 到 4 項，並附上實際檢查過的檔案與總表章節。由 diff-review 交接時，把發現與待確認項目原樣交回，由它合併。
- diff 沒有碰到任何輸入、驗證、授權、檔案、對外請求、秘密、加密、依賴或部署設定時，回報「這個 diff 沒有資安相關的改動」並寫出判斷依據，不做完整流程。

## Output Contract

報告依序包含：

1. **結論**：各等級的發現數、已修補數、仍待處理的最高等級。
2. **範圍與依據**：掃了哪些目錄與服務、使用的清單（名稱、版本、網址、抓取日期）、執行的工具與版本、沒抓到或沒執行的項目與原因。
3. **發現**：由 P0 到 P3，每筆用核心 [Findings and Severity](../software-engineering-guidelines/SKILL.md#findings-and-severity) 的格式，另附類別（清單項目編號與 CWE）、攻擊者需要的條件、修補內容與驗證結果。秘密的寫法照核心的 [Secrets](../software-engineering-guidelines/SKILL.md#secrets)。
4. **待確認**：同一格式的 `NEEDS INVESTIGATION` 項目。
5. **強化建議**：不構成漏洞但值得做的防護，以及建議安裝的掃描工具。
6. **清單對照表**：每份清單逐項的結論，以及總表各節是否適用。

報告預設放在對話裡。使用者要留存時，寫到專案既有的文件位置；沒有既定位置就寫到 `docs/security-scan/report.md`，再次掃描時就地更新。

## Quality Rules

- 沒有程式碼位置與觸發路徑的項目，不列為發現。
- 「已檢查無發現」要寫出實際看過的位置。沒看過的寫「未檢查」。
- 清單的版本以當次抓到的為準。沒有抓到最新版時明說，不寫成已對照最新版。
- 不把掃描工具的輸出原樣當成結論，也不因為工具沒報就宣稱安全。
- 掃描完成不等於系統安全。報告寫明這次沒有涵蓋的範圍，例如正式環境設定、第三方服務、實體與人員層面。

## Common Mistakes

| 錯誤 | 正確做法 |
|---|---|
| 只搜尋 `eval`、`exec` 這類關鍵字就交差 | 從每個入口追資料流，授權與邏輯問題要讀流程 |
| 用記憶中的舊版排名 | 每次從入口頁抓當下的版本 |
| 依賴稽核列出幾十筆就全部標成 P0 | 逐筆確認專案是否用到受影響的功能 |
| 找到一處就修那一處 | 搜尋同樣的寫法，一次修完 |
| 把秘密從程式刪掉就當作修好 | 請使用者撤銷並輪替 |
| 在正式環境試攻擊請求 | 只在本機或測試環境重現 |
| diff 模式只看 diff 裡的那幾行 | 追到 diff 之外的來源與去向，漏洞常在改動與既有程式的交界 |
| 修完沒有重跑重現步驟 | 每個修補都要有修補前失敗、修補後通過的證據 |

## Suggested Prompt

```text
幫我對這個專案做資安掃描，找到的漏洞直接修，修完驗證。
只掃 api/ 目錄，先給我報告，不要動程式。
```

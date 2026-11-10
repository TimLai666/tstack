# 要抓的清單與入口

這些清單會改版，排名與項目都會變。每次掃描都從下列入口頁抓當下的最新版，不使用記憶中的版本，也不把年份寫死在網址裡。入口頁會轉址時跟著轉址走。

## 抓取規則

1. 依專案類型從下表選出適用的清單，「所有專案」那幾列每次都抓。
2. 從入口頁找出最新的正式版，記下清單名稱、版本或年份、實際網址與抓取日期。候選版與草稿只在沒有正式版時使用，並在報告標明。
3. 把清單上的每一項轉成本次的檢查項目，項目編號照原清單（例如 `CWE-79`、`A01`、`API1`）。
4. 清單上有、[漏洞總表](vulnerability-catalog.md)沒有的項目，照清單原文的說明檢查，並在報告的「總表未涵蓋」列出。
5. 抓不到時換一個可用的抓取工具再試一次。仍抓不到就只用漏洞總表，並在報告寫明哪幾份清單沒有更新到、原因是什麼。不得用記憶中的排名冒充最新版。
6. 這裡沒列、但更貼近專案技術的清單（語言、框架、雲端平台、產業法規），找得到權威來源就加進來，並在報告列出來源。

## 所有專案

| 清單 | 入口 | 用途 |
|---|---|---|
| CWE Top 25 Most Dangerous Software Weaknesses | https://cwe.mitre.org/top25/ | 最常見且危害最大的弱點類型 |
| CWE Top 10 KEV Weaknesses | https://cwe.mitre.org/top25/ （同頁連結） | 實際被拿來攻擊的弱點類型，排修補順序時加權 |
| CWE "On the Cusp" | https://cwe.mitre.org/top25/ （同頁連結） | 差一點進榜的弱點，補足 Top 25 |
| OWASP Top 10 | https://owasp.org/www-project-top-ten/ | 網頁應用的主要風險類別 |
| OWASP Top 10 Proactive Controls | https://owasp.org/www-project-proactive-controls/ | 修補時該採用的防護做法 |
| OWASP Cheat Sheet Series | https://cheatsheetseries.owasp.org/ | 各類漏洞的具體修法 |
| CISA Known Exploited Vulnerabilities Catalog | https://www.cisa.gov/known-exploited-vulnerabilities-catalog | 依賴套件的 CVE 是否已有人在利用 |
| OSV | https://osv.dev/ | 依賴套件的已知漏洞 |
| GitHub Advisory Database | https://github.com/advisories | 依賴套件的已知漏洞與修補版本 |

## 依專案類型加選

| 專案有這個 | 清單 | 入口 |
|---|---|---|
| HTTP API、GraphQL、gRPC | OWASP API Security Top 10 | https://owasp.org/API-Security/ |
| 瀏覽器端大量 JavaScript | OWASP Top 10 Client-Side Security Risks | https://owasp.org/www-project-top-10-client-side-security-risks/ |
| 金流、點數、優惠、庫存等流程 | OWASP Top 10 for Business Logic Abuse | https://owasp.org/www-project-top-10-for-business-logic-abuse/ |
| 呼叫 LLM、RAG、生成內容 | OWASP Top 10 for LLM Applications | https://genai.owasp.org/llm-top-10/ |
| 會自己呼叫工具或執行動作的 agent | OWASP Top 10 for Agentic Applications | https://genai.owasp.org/initiatives/agentic-security-initiative/ |
| 提供或使用 MCP server | OWASP MCP Top 10 | https://owasp.org/www-project-mcp-top-10/ |
| 自己訓練或微調模型 | OWASP Machine Learning Security Top 10 | https://owasp.org/www-project-machine-learning-security-top-10/ |
| iOS、Android app | OWASP Mobile Top 10、MASVS | https://owasp.org/www-project-mobile-top-10/ 、 https://owasp.org/www-project-mobile-app-security/ |
| 桌面應用（含 Electron、Tauri） | OWASP Desktop App Security Top 10 | https://owasp.org/www-project-desktop-app-security-top-10/ |
| CI/CD 設定檔 | OWASP Top 10 CI/CD Security Risks | https://owasp.org/www-project-top-10-ci-cd-security-risks/ |
| Dockerfile、映像檔 | OWASP Docker Top 10 | https://owasp.org/www-project-docker-top-10/ |
| Kubernetes 設定 | OWASP Kubernetes Top Ten | https://owasp.org/www-project-kubernetes-top-ten/ |
| 無伺服器函式 | OWASP Serverless Top 10 | https://owasp.org/www-project-serverless-top-10/ |
| 服務帳號、API 金鑰、機器對機器授權 | OWASP Non-Human Identities Top 10 | https://owasp.org/www-project-non-human-identities-top-10/ |
| 自管主機、網路設備設定 | OWASP Top 10 Infrastructure Security Risks | https://owasp.org/www-project-top-10-infrastructure-security-risks/ |
| 智慧合約 | OWASP Smart Contract Top 10 | https://owasp.org/www-project-smart-contract-top-10/ |
| 韌體、硬體描述語言、驅動程式 | CWE Most Important Hardware Weaknesses | https://cwe.mitre.org/topHW/index.html |

## 需要逐條驗證時

使用者要的是完整查核而不只是找漏洞時，改用驗證標準逐條對照：

| 標準 | 入口 | 適用 |
|---|---|---|
| OWASP ASVS | https://owasp.org/www-project-application-security-verification-standard/ | 網頁應用與 API 的逐條安全要求 |
| OWASP MASVS | https://owasp.org/www-project-mobile-app-security/ | 行動 app 的逐條安全要求 |
| OWASP Web Security Testing Guide | https://owasp.org/www-project-web-security-testing-guide/ | 每一類漏洞的測試方法 |

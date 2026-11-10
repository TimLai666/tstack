# 掃描工具對照

工具掃描這條線用這張表。先看專案用了什麼，再逐一確認對應的工具能不能用，能用的都跑。

## 使用規則

1. 依專案裡實際存在的檔案判斷適用哪幾列，不靠猜。
2. 逐一確認工具可用：隨語言工具鏈附帶的直接可用；獨立工具用 shell 的指令解析確認有沒有安裝，並看專案的設定檔、CI 設定與套件腳本有沒有已經接好的掃描指令。專案接好的指令優先，照它的參數跑。
3. 可用的都跑。參數與輸出格式看該工具自己的 `--help`，這裡只列名稱。
4. 沒安裝的不自行安裝，列進報告的建議，寫明它能補上哪一塊。
5. 每一筆輸出都回到程式碼確認後才算發現。工具沒有報告不代表沒有漏洞。
6. 報告的「範圍與依據」列出每個工具的名稱、版本、有沒有跑、沒跑的原因。

## 依賴套件的已知漏洞

| 專案裡有 | 隨工具鏈附帶 | 獨立工具 |
|---|---|---|
| `package-lock.json` | `npm audit` | |
| `pnpm-lock.yaml` | `pnpm audit` | |
| `yarn.lock` | `yarn npm audit`（Yarn 2 以上）、`yarn audit`（Yarn 1） | |
| `bun.lock`、`bun.lockb` | `bun audit` | |
| `requirements*.txt`、`pyproject.toml`、`poetry.lock`、`uv.lock` | | `pip-audit` |
| `go.mod` | | `govulncheck` |
| `Cargo.lock` | | `cargo audit`、`cargo deny` |
| `Gemfile.lock` | | `bundler-audit` |
| `composer.lock` | `composer audit` | |
| `*.csproj`、`packages.lock.json` | `dotnet list package --vulnerable --include-transitive` | |
| `pom.xml`、`build.gradle*` | | OWASP Dependency-Check 的 Maven 或 Gradle 外掛 |
| 以上任何一種，或多種語言混用 | | `osv-scanner`、`trivy fs`、`grype` |

沒有 lockfile 時先在報告指出這件事：版本沒有鎖定，稽核結果只代表當下解析到的版本。

程式碼託管平台如果已經開了依賴掃描，一併讀它的結果：GitHub 的 Dependabot 警示、GitLab 的依賴掃描報告。用該平台的 CLI 或 API 讀，讀不到就在報告寫明。

## 秘密

| 範圍 | 工具 |
|---|---|
| 工作目錄與完整的 git 歷史 | `gitleaks`、`trufflehog` |
| 平台已開的秘密掃描 | GitHub 的 secret scanning 警示、GitLab 的秘密偵測報告 |

兩個工具都沒有時，改用搜尋找常見的金鑰格式與 `password`、`secret`、`token`、`api_key` 這類名稱，並說明這只涵蓋目前的檔案，沒有涵蓋歷史紀錄。秘密的寫法照核心的 [Secrets](../../software-engineering-guidelines/SKILL.md#secrets)。

## 靜態分析

| 專案裡有 | 工具 |
|---|---|
| 任何語言 | `semgrep`、CodeQL |
| Python | `bandit` |
| Go | `gosec` |
| Ruby on Rails | `brakeman` |
| JavaScript、TypeScript | 專案 ESLint 設定裡的安全規則外掛 |
| Java、Kotlin | SpotBugs 搭配 Find Security Bugs |
| C、C++ | 編譯器的警告與分析選項、`cppcheck`、`clang-tidy` |

專案的 linter 與型別檢查若已包含安全規則，照專案的指令跑一次並讀結果。

## 容器、基礎設施與 CI 設定

| 專案裡有 | 工具 |
|---|---|
| `Dockerfile` | `hadolint`、`trivy config` |
| 已建好的映像檔 | `trivy image`、`grype`、`docker scout` |
| Terraform、CloudFormation、Kubernetes 設定、Helm chart | `trivy config`、`checkov`、`tfsec`、`kubesec` |
| GitHub Actions 的 workflow | `zizmor`、`actionlint` |

## 執行中的服務

只在本機或測試環境使用，而且使用者同意時才跑。不對正式環境與第三方服務執行。

| 目標 | 工具 |
|---|---|
| 本機啟動的網頁應用或 API | OWASP ZAP 的基準掃描、`nuclei` |
| TLS 設定 | `testssl.sh` |

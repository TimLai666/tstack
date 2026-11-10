# Scan Tools

Use these tables for the tool scan track. First see what the project uses, then confirm one by one whether the matching tools are usable, and run every usable one.

## Usage rules

1. Decide which rows apply from the files that actually exist in the project, not by guessing.
2. Confirm one by one that each tool is usable: tools that ship with a language toolchain are usable directly; for a standalone tool, confirm whether it is installed with the shell's command resolution, and check whether the project's configuration files, CI configuration and package scripts already have a scan command wired up. A command the project has wired up takes priority; run it with its arguments.
3. Run every usable tool. For arguments and output formats, see the tool's own `--help`; only names are listed here.
4. Do not install a tool that is not installed yourself. List it in the report's recommendations, stating which gap it would cover.
5. Every output item counts as a finding only after it is confirmed against the code. A tool reporting nothing does not mean there is no vulnerability.
6. The report's "Scope and basis" lists each tool's name and version, whether it was run, and why it was not run.

## Known vulnerabilities in dependencies

| The project has | Ships with the toolchain | Standalone tool |
|---|---|---|
| `package-lock.json` | `npm audit` | |
| `pnpm-lock.yaml` | `pnpm audit` | |
| `yarn.lock` | `yarn npm audit` (Yarn 2 and later), `yarn audit` (Yarn 1) | |
| `bun.lock`, `bun.lockb` | `bun audit` | |
| `requirements*.txt`, `pyproject.toml`, `poetry.lock`, `uv.lock` | | `pip-audit`. It reads requirements files or an installed environment; when there is only `poetry.lock` or `uv.lock`, first export requirements with that tool, or audit an already installed environment instead |
| `go.mod` | | `govulncheck` |
| `Cargo.lock` | | `cargo audit`, `cargo deny` |
| `Gemfile.lock` | | `bundler-audit` |
| `composer.lock` | `composer audit` | |
| `*.csproj`, `packages.lock.json` | `dotnet list package --vulnerable --include-transitive` | |
| `pom.xml`, `build.gradle*` | | The OWASP Dependency-Check Maven or Gradle plugin |
| Any of the above, or several languages mixed | | `osv-scanner`, `trivy fs`, `grype` |

When there is no lockfile, first point this out in the report: versions are not locked, and the audit result only covers the versions resolved at that moment.

When the code hosting platform already has dependency scanning enabled, read its results as well: GitHub's Dependabot alerts, GitLab's dependency scanning report. Read them with that platform's CLI or API; when they cannot be read, state so in the report.

## Secrets

| Scope | Tool |
|---|---|
| Working directory and full git history | `gitleaks`, `trufflehog` |
| Secret scanning already enabled on the platform | GitHub's secret scanning alerts, GitLab's secret detection report |

When neither tool is available, search instead for common key formats and names like `password`, `secret`, `token`, `api_key`, and state that this covers only the current files, not the history. Write secrets as the core [Secrets](../../software-engineering-guidelines/SKILL.md#secrets) requires.

## Static analysis

| The project has | Tool |
|---|---|
| Any language | `semgrep`, CodeQL |
| Python | `bandit` |
| Go | `gosec` |
| Ruby on Rails | `brakeman` |
| JavaScript, TypeScript | Security rule plugins in the project's ESLint configuration |
| Java, Kotlin | SpotBugs with Find Security Bugs |
| C, C++ | Compiler warning and analysis options, `cppcheck`, `clang-tidy` |

When the project's linter and type checking already include security rules, run them once with the project's commands and read the results.

## Containers, infrastructure and CI configuration

| The project has | Tool |
|---|---|
| `Dockerfile` | `hadolint`, `trivy config` |
| Built images | `trivy image`, `grype`, `docker scout` |
| Terraform, CloudFormation, Kubernetes configuration, Helm charts | `trivy config`, `checkov`, `kubesec` |
| GitHub Actions workflows | `zizmor`, `actionlint` |

## Running services

Run these only locally or in a test environment, and only when the user agrees. Do not run them against production or third-party services.

| Target | Tool |
|---|---|
| Web application or API started locally | OWASP ZAP baseline scan, `nuclei` |
| TLS configuration | `testssl.sh` |

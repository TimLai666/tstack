# Lists to Fetch and Their Entry Pages

These lists are revised, and their rankings and items change. On every scan, fetch the current latest edition from the entry pages below. Do not use an edition from memory, and do not hard-code a year in a URL. When an entry page redirects, follow the redirect.

## Fetch rules

1. Select the applicable lists from the tables below by project type. Fetch the "All projects" rows every time.
2. From the entry page, find the latest official edition, and record the list name, version or year, actual URL and fetch date. Use a candidate or draft edition only when there is no official edition, and say so in the report.
3. Turn every item on a list into a check item for this scan, numbered as in the original list (for example `CWE-79`, `A01`, `API1`).
4. For an item that is on a list but not in the [vulnerability catalog](vulnerability-catalog.md), check it according to the list's own description, and list it under "Not covered by the catalog" in the report.
5. When a list cannot be fetched, try once more with another available fetch tool. When it still cannot be fetched, use only the vulnerability catalog, and state in the report which lists were not updated and why. A ranking from memory MUST NOT be passed off as the latest edition.
6. When a list not given here is closer to the project's technology (language, framework, cloud platform, industry regulation) and an authoritative source can be found, add it, and list the source in the report.

## All projects

| List | Entry page | Purpose |
|---|---|---|
| CWE Top 25 Most Dangerous Software Weaknesses | https://cwe.mitre.org/top25/ | The most common and most harmful weakness types |
| CWE Top 10 KEV Weaknesses | https://cwe.mitre.org/top25/ (linked from the same page) | Weakness types actually used in attacks; weight them when ordering fixes |
| CWE "On the Cusp" | https://cwe.mitre.org/top25/ (linked from the same page) | Weaknesses that narrowly missed the ranking; supplement the Top 25 |
| OWASP Top 10 | https://owasp.org/www-project-top-ten/ | The main risk categories for web applications |
| OWASP Top 10 Proactive Controls | https://owasp.org/www-project-proactive-controls/ | Protections to adopt when fixing |
| OWASP Cheat Sheet Series | https://cheatsheetseries.owasp.org/ | Concrete fixes for each vulnerability type |
| CISA Known Exploited Vulnerabilities Catalog | https://www.cisa.gov/known-exploited-vulnerabilities-catalog | Whether a dependency's CVE is already being exploited |
| OSV | https://osv.dev/ | Known vulnerabilities in dependencies |
| GitHub Advisory Database | https://github.com/advisories | Known vulnerabilities in dependencies and their fixed versions |

## Additional lists by project type

| The project has | List | Entry page |
|---|---|---|
| HTTP API, GraphQL, gRPC | OWASP API Security Top 10 | https://owasp.org/API-Security/ |
| A lot of browser-side JavaScript | OWASP Top 10 Client-Side Security Risks | https://owasp.org/www-project-top-10-client-side-security-risks/ |
| Payment, points, discount, inventory or similar flows | OWASP Top 10 for Business Logic Abuse | https://owasp.org/www-project-top-10-for-business-logic-abuse/ |
| LLM calls, RAG, generated content | OWASP Top 10 for LLM Applications | https://genai.owasp.org/llm-top-10/ |
| Agents that call tools or take actions on their own | OWASP Top 10 for Agentic Applications | https://genai.owasp.org/initiatives/agentic-security-initiative/ |
| Provides or uses an MCP server | OWASP MCP Top 10 | https://owasp.org/www-project-mcp-top-10/ |
| Trains or fine-tunes its own models | OWASP Machine Learning Security Top 10 | https://owasp.org/www-project-machine-learning-security-top-10/ |
| iOS or Android app | OWASP Mobile Top 10, MASVS | https://owasp.org/www-project-mobile-top-10/ , https://owasp.org/www-project-mobile-app-security/ |
| Desktop application (including Electron, Tauri) | OWASP Desktop App Security Top 10 | https://owasp.org/www-project-desktop-app-security-top-10/ |
| CI/CD configuration files | OWASP Top 10 CI/CD Security Risks | https://owasp.org/www-project-top-10-ci-cd-security-risks/ |
| Dockerfile, images | OWASP Docker Top 10 | https://owasp.org/www-project-docker-top-10/ |
| Kubernetes configuration | OWASP Kubernetes Top Ten | https://owasp.org/www-project-kubernetes-top-ten/ |
| Serverless functions | OWASP Serverless Top 10 | https://owasp.org/www-project-serverless-top-10/ |
| Service accounts, API keys, machine-to-machine authorization | OWASP Non-Human Identities Top 10 | https://owasp.org/www-project-non-human-identities-top-10/ |
| Self-managed hosts, network device configuration | OWASP Top 10 Infrastructure Security Risks | https://owasp.org/www-project-top-10-infrastructure-security-risks/ |
| Smart contracts | OWASP Smart Contract Top 10 | https://owasp.org/www-project-smart-contract-top-10/ |
| Firmware, hardware description languages, drivers | CWE Most Important Hardware Weaknesses | https://cwe.mitre.org/topHW/index.html |

## When item-by-item verification is needed

When the user wants a full verification rather than only a vulnerability hunt, check item by item against a verification standard instead:

| Standard | Entry page | Applies to |
|---|---|---|
| OWASP ASVS | https://owasp.org/www-project-application-security-verification-standard/ | Item-by-item security requirements for web applications and APIs |
| OWASP MASVS | https://owasp.org/www-project-mobile-app-security/ | Item-by-item security requirements for mobile apps |
| OWASP Web Security Testing Guide | https://owasp.org/www-project-web-security-testing-guide/ | Test methods for each vulnerability type |

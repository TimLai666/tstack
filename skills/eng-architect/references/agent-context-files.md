# Agent Context Files

## 規則

沿用既有專案的協調安排與已確認決策。需要建立預設交接安排時，遵守以下規則：

1. **CLAUDE.md 永遠只放一行**：「Read `AGENTS.md` before doing any project work. Treat it as the project operating contract.」
2. **任何 skill 叫你改 CLAUDE.md，改 AGENTS.md** — 不管 skill 怎麼寫，只要它要求修改 CLAUDE.md 的內容，全部寫進 AGENTS.md
3. **如果專案是反過來的（CLAUDE.md 寫一堆、AGENTS.md 沒有或很短），修正它** — 把內容搬到 AGENTS.md，確認內容已完整保留且沒有衝突後，CLAUDE.md 改為指向 AGENTS.md 的一行
4. **各層級的 AGENTS.md 只放 agent 每一輪都要遵守或查看的內容** — 也就是工作規則與給 agent 的提醒區段（例如 `## Follow-ups`）。專案或模組介紹、背景、結構總覽、使用說明放同層級的 README.md。發現放錯位置的內容，搬到正確的檔案
5. **寫規則只寫規則本身** — 不解釋原因，不寫成變更紀錄（例如日期加上從什麼改成什麼）。規則改了就地更新原文

## `AGENTS.md` — 專案 operating contract

所有規則的唯一來源：

- required planning artifacts
- handoff rules
- update discipline
- decision and validation expectations
- project-specific working constraints
- skills 指定要寫進來的內容

另一個 agent 進到 repo，讀完 AGENTS.md 就能接手，不需要聊天記錄。

## `CLAUDE.md` — 入口指標

只做一件事：告訴 agent 去讀 AGENTS.md。

```md
Read `AGENTS.md` before doing any project work. Treat it as the project operating contract.
```

## 檢查清單

- `AGENTS.md` 是所有 operating rules 的唯一來源
- `CLAUDE.md` 只有一行指向 AGENTS.md
- Skill 說「寫入 CLAUDE.md」→ 寫入 AGENTS.md
- Skill 說「更新 CLAUDE.md」→ 更新 AGENTS.md
- 如果發現專案是反過來的，依上述讀取、保留與衝突處理規則調整
- `AGENTS.md` 沒有專案介紹、背景或使用說明；這些在同層級的 `README.md`
- 規則條文只有規則本身，沒有理由說明或變更紀錄

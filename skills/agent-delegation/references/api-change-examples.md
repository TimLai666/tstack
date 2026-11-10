# 介面變更提案示例

主 agent 在諮詢並修正初案後，依實際改動選用下列呈現方式，合併原本待使用者決定的事項。以下都是假設案例，不是已發生的變更或模型諮詢紀錄；實際提案使用查證過的現有程式，並標明建議稿。

## 名稱、簽名與用法

**假設需求：** 讓呼叫端看得出第二個參數的意思。

改前：

```ts
listUsers(20, true);
```

建議改後：

```ts
listUsers({ limit: 20, includeDisabled: true });
```

| 比較項目 | 改前 | 建議改後 |
| --- | --- | --- |
| 簽名 | `listUsers(limit: number, includeDisabled: boolean): User[]` | `listUsers(options: ListUsersOptions): User[]` |
| 參數結構 | 兩個位置參數 | `ListUsersOptions` 包含 `limit: number` 與 `includeDisabled: boolean` |
| 相同行為 | 最多回傳 20 位使用者，包含停用帳號 | 維持相同結果 |
| 呼叫端影響 | 現有呼叫可用 | 必須更新呼叫方式，或保留舊簽名的相容入口 |

提案須交代初案經諮詢後改了什麼、採納依據及未採納的重要建議，再提出選擇。例如在所有呼叫端都由同一專案管理且能一起更新的前提下，可建議一次更新；存在外部呼叫端時，應說明相容入口與遷移安排，再請使用者決定。

## 簽名不變，行為改變

**假設需求：** 設定檔遺失時，讓呼叫端明確處理錯誤。

改前與建議改後都使用 `loadSettings(path: string): Settings`，但結果不同：

| 相同輸入 | 改前 | 建議改後 |
| --- | --- | --- |
| `loadSettings("missing.json")`，檔案不存在 | 回傳預設設定 | 拋出 `SettingsNotFoundError` |

改前使用：

```ts
const settings = loadSettings("missing.json"); // 取得預設設定
```

建議改後使用：

```ts
try {
  const settings = loadSettings("missing.json");
} catch (error) {
  if (error instanceof SettingsNotFoundError) {
    showConfigurationError();
  } else {
    throw error;
  }
}
```

提案須說明既有呼叫端若不處理錯誤會受到什麼影響，附上經諮詢修正的建議，並讓使用者決定是否採用。函數名稱與簽名相同，仍須依行為差異觸發諮詢。

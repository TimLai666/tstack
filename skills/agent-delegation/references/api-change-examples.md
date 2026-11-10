# Interface change proposal examples

After consulting and revising the first draft, the main agent chooses from the presentations below according to the actual change, and combines it with the items that were already waiting for the user's decision. All of the following are hypothetical cases, not changes that happened or records of model consultations; an actual proposal uses verified existing code and is marked as a proposed draft.

## Name, signature and usage

**Hypothetical requirement:** let callers see what the second parameter means.

Before:

```ts
listUsers(20, true);
```

Proposed:

```ts
listUsers({ limit: 20, includeDisabled: true });
```

| Item | Before | Proposed |
| --- | --- | --- |
| Signature | `listUsers(limit: number, includeDisabled: boolean): User[]` | `listUsers(options: ListUsersOptions): User[]` |
| Parameter structure | Two positional parameters | `ListUsersOptions` contains `limit: number` and `includeDisabled: boolean` |
| Same behavior | Returns at most 20 users, including disabled accounts | Same result |
| Impact on callers | Existing calls work | Calls have to be updated, or a compatibility entry point with the old signature is kept |

The proposal MUST state what the consultation changed in the first draft, the basis for what was adopted and the important suggestions not adopted, and then present the choice. For example, when all callers are managed in the same project and can be updated together, it may recommend updating them all at once; when external callers exist, it SHOULD describe the compatibility entry point and the migration plan, then ask the user to decide.

## Same signature, changed behavior

**Hypothetical requirement:** when the settings file is missing, make callers handle the error explicitly.

Both before and after use `loadSettings(path: string): Settings`, but the results differ:

| Same input | Before | Proposed |
| --- | --- | --- |
| `loadSettings("missing.json")`, file does not exist | Returns the default settings | Throws `SettingsNotFoundError` |

Usage before:

```ts
const settings = loadSettings("missing.json"); // gets the default settings
```

Proposed usage:

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

The proposal MUST state what happens to existing callers that do not handle the error, attach the suggestion as revised by the consultation, and let the user decide whether to adopt it. Even when the function name and signature stay the same, the behavior difference MUST still trigger consultation.

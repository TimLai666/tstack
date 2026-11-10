# Legacy status migration

Earlier versions used `delivery-plan.md` for status. It must not be mistaken for a feature plan by a `*-plan.md` search.

Read the existing file, project instructions, and project memory before changing it. Confirm that `delivery-plan.md` is the legacy status record, not a feature plan. Reuse an existing user decision about migration. If none exists, explain the change to `delivery-status.md` and ask whether the user wants to migrate. Wait for their decision before renaming or replacing the status record. Continue independent work using the existing record while waiting.

After the user decides, record their choice to migrate, keep the old name, or defer in project memory through **project-memory**, using the preference key `delivery-status-migration` and source `eng-architect`. Include the chosen status path and any condition for revisiting the decision. Record the decision separately from execution: approval does not mean migration has completed. Read this entry on later encounters and do not ask again unless the user reopens the decision or its stated condition is met. If memory cannot be saved, report that limitation instead of claiming the decision was recorded.

When migration is approved, preserve the content with `git mv` for a tracked file and update affected references in the authorized scope. If both names exist, compare them and resolve their roles before writing; do not overwrite or leave competing status sources. If the user keeps or defers the old arrangement, continue using it without creating a competing `delivery-status.md`.

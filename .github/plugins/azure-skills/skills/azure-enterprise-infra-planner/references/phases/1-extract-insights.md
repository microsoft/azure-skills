# Phase 1: Extract Insights

> The goal of this phase is to extract insights from the user's existing Azure environment. These insights will be used to guide the planning process in later phases.

1. Check whether insights already exist at `<project-root>/.azure/insights.json`. If they do, reuse them and skip the rest of this phase.
2. Check whether the `insights_get` tool is available. If it is not, skip this phase.
3. Ask the user which scope to use for generating insights. Present these three options:
   a. "Subscription-scoped (default subscription)" — use this as the default if the user does not respond.
   b. "Subscription-scoped (choose a subscription)" — if selected, ask the user to provide a subscription name or ID.
   c. "Tenant-scoped (slower)"
4. Ask the user whether there are specific areas they want the insights to focus on. Present these options:
   a. "General" — use this as the default if the user does not respond.
   b. "Cost"
   c. "Reliability"
   d. "Security"
   e. "Performance"
   f. "Other" — this should be a custom input field.
5. Run the `insights_get` tool using a general-purpose subagent. Pass a one-line summary via the `--query` option that describes the user's infrastructure and the types of insights to prioritise. Do not pass the `--nocache` flag unless the user has explicitly asked for it. Begin Phase 2 while this tool runs.
6. Once the tool finishes, save the resulting JSON to `<project-root>/.azure/insights.json`. Do not include tool call metadata. If the tool errors or returns no insights, write an empty array `[]` to the file instead.

## Gate

- `insights.json` must exist and match the Insights Schema defined in [schema.md](../schema.md). If the tool errored or returned no insights, the file should contain an empty array `[]`.
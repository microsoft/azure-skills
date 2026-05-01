# Custom Template Adaptation

For the EXTEND path — when the user has existing Bicep or Terraform templates.

## Instructions

1. **Read** the user's existing template files. Understand the resource graph: what's defined, how resources reference each other, what naming conventions are used.

2. **Analyze** the template against the user's requirements (from [intake.md](intake.md)) and the Foundry private networking documentation validated in the intake step. Identify:
   - Resources already present and correctly configured
   - Resources present but misconfigured (wrong settings, missing properties)
   - Resources missing entirely
   - Dependency or wiring issues (e.g., PEs referencing wrong subnet, DNS zones not linked)

3. **Present** findings to the user as a gap analysis table: resource, status (✅ present / ⚠️ misconfigured / ❌ missing), and what needs to change. Include any issues found.

4. **Propose** an end-to-end plan to address all gaps — ordered by dependency. Explain what will be added, what will be modified, and why. Never overwrite existing modules — add alongside and reference existing resources.

5. **Wait** for user approval before making any changes.

6. **Implement** the approved changes. After implementation, the flow continues to Step 4 (Pre-Deployment Validation) in the main workflow.

## Retry Safety

> ⚠️ If a deployment fails after the capability host step starts, Azure Container Apps leaves a `legionservicelink` service association on the agent subnet that **cannot be removed**. On retry, use a **new subnet or new VNet** — never reuse the same agent subnet.


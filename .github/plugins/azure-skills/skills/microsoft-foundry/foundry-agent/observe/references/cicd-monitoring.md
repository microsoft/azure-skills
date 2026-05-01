# Step 6 — CI/CD Evals & Continuous Production Monitoring

After confirming the final agent version through the observe loop, present two complementary monitoring options. The user may choose one, both, or neither.

## Option 1 — CI/CD Pipeline Evaluations (Pre-Deploy Gate)

*"Would you like to add automated evaluations to your CI/CD pipeline so every deployment is evaluated before going live?"*

CI/CD evals run batch evaluations as part of your deployment pipeline, catching regressions **before** they reach production.

If yes, generate a GitHub Actions workflow (for example, `.github/workflows/agent-eval.yml`) that:

1. Triggers on push to `main` or on pull request
2. Accepts a metadata-file input or environment variable such as `FOUNDRY_METADATA_FILE` and defaults it to `.foundry/agent-metadata.yaml`
3. Reads evaluation-suite definitions from the selected metadata file (for example, `.foundry/agent-metadata.prod.yaml` for prod CI)
4. Reads evaluator definitions from `.foundry/evaluators/` and test datasets from `.foundry/datasets/`
5. Runs `evaluation_agent_batch_eval_create` against the newly deployed agent version
6. Fails the workflow if any evaluator score falls below the configured thresholds for the environment and evaluation suite resolved from that metadata file
7. Posts a summary as a PR comment or workflow annotation

Use repository secrets for the selected environment's project endpoint and Azure credentials, and keep the metadata filename explicit in the workflow so prod rollouts do not depend on the local/dev default file. Confirm the workflow file with the user before committing.

## Option 2 — Continuous Production Monitoring (Post-Deploy)

*"Would you like to set up continuous evaluations to monitor your agent's quality in production?"*

Continuous evaluation uses Foundry-native MCP tools to automatically assess agent responses on an ongoing basis — no additional CI/CD pipeline setup is needed for this option. This catches regressions that emerge **after** deployment from changing data, user patterns, or upstream service drift.

### Enable Continuous Evaluation

Use the [continuous evaluation reference](continuous-eval.md) to configure monitoring. The workflow:

1. **Check existing config** — call `continuous_eval_get` to see if monitoring is already active.
2. **Select evaluators** — recommend starting with the same evaluators used in batch evals for consistent comparison:
   - **Quality evaluators** (require `deploymentName`): e.g., groundedness, coherence, relevance, task_adherence
   - **Safety evaluators**: e.g., violence, indirect_attack, hate_unfairness
3. **Enable** — call `continuous_eval_create` with the selected evaluators. The tool auto-detects agent kind and configures the appropriate backend (real-time for prompt agents, scheduled for hosted agents).
4. **Confirm** — present the returned configuration to the user.

### Acting on Monitoring Results

Monitoring is only complete when score drops trigger investigation and remediation.

For instructions on how to read evaluation scores, triage regressions, and verify fixes, see [Acting on Results](continuous-eval.md#acting-on-results).

The observe loop does not end at deployment. Continuous monitoring closes the loop: **observe → optimize → deploy → monitor → observe**. Always offer to set up monitoring after completing an optimization cycle.

## Reference

- [Microsoft Foundry Cloud Evaluation](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/cloud-evaluation)
- [Hosted Agents](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents)
- [Continuous Evaluation Reference](continuous-eval.md)

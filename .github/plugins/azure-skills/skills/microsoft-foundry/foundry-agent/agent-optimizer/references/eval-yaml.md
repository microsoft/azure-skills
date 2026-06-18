# eval.yaml Guidance

Create `eval.yaml` directly when the conversation or `.foundry/agent-metadata*.yaml` already selected the dataset/evaluators. Otherwise ask whether to run `azd ai agent eval generate` or let optimize use built-in defaults.

## Include

```yaml
name: <suite-or-optimization-name>
agent:
  name: <agent-name>
  kind: hosted
  version: "<agent-version>"
  model: <baseline-model-deployment-name>
  config: .agent_configs/baseline/metadata.yaml
dataset:
  local_uri: <path-to-jsonl>
  # name: <foundry-dataset-name>
  # version: "<dataset-version>"
# validation_dataset:
#   name: <validation-dataset-name>
#   version: "<validation-version>"
evaluators:
  - <evaluator-name>
  - name: <custom-evaluator-name>
    version: "<evaluator-version>"
    local_uri: <local-evaluator-json>
options:
  eval_model: <existing-chat-model-deployment-name>
  optimization_model: <allowed-optimizer-model-deployment-name>
  max_candidates: 4
  optimization_config:
    model_search_space:
      - <target-model-deployment-name>
```

Use existing model deployments for `agent.model` and `options.eval_model`; do not assume `gpt-4o`.

For `options.optimization_model`, first verify that the target Foundry project has a deployment whose name is in this allowlist:

- `GPT-5`
- `GPT-5.1`
- `GPT-5.2`
- `GPT-5.4`
- `GPT-5.5`
- `DeepSeek-V4-Pro`
- `DeepSeek-V-3.2`

If none exist, ask the user to deploy one before configuring optimization. Use `options.optimization_config.model_search_space` only for target model candidates that exist in the project; it may include the baseline model when the user wants it compared.

## Generate evals when inputs are missing

Prefer `eval generate` over older init flows:

```bash
azd ai agent eval generate --dataset <path-to-jsonl>
azd ai agent eval generate --reset-defaults
```

After generation, run `azd ai agent optimize --optimize-model <allowed-optimizer-model-deployment-name>` from the azd project; optimize auto-detects the generated `eval.yaml`.

## Skip

Do not add these fields unless the user explicitly asks and understands the tradeoff:

- `target_attributes`
- `budget`
- `min_improvement`
- `pass_threshold`
- `keep_versions`
- `generation_instruction`
- `max_samples`
- `trace_days`
- legacy `dataset_file`, `dataset_reference`, or `validation_reference` when writing a new file

Keep `target_attributes` omitted so azd can auto-detect optimizable attributes.

## Source mapping

| Source | eval.yaml field |
|--------|-----------------|
| effective azd context | `agent.name`, `agent.version`, `agent.kind` |
| baseline config | `agent.model`, `agent.config` |
| selected local dataset JSONL | `dataset.local_uri` |
| selected remote/local dataset | `dataset.name`, `dataset.version`, `dataset.local_uri` |
| selected validation dataset | `validation_dataset` |
| selected Foundry/local evaluators | `evaluators[]` |
| selected judge/eval deployment | `options.eval_model` |
| selected optimizer deployment | `options.optimization_model` |
| selected target model candidates | `options.optimization_config.model_search_space` |

Treat older `dataset_file`, `dataset_reference`, `validation_reference`, `max_iterations`, and `optimization_config.model` as legacy inputs when reading existing files, but write new files with the current contract above.

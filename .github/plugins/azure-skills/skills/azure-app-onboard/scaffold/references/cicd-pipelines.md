# CI/CD Pipeline Patterns

CI/CD is deferred to v2. Do NOT auto-generate workflow files.

If the user requests CI/CD guidance, call `mcp_azure_mcp_deploy` → `deploy_pipeline_guidance_get` with `is-azd-project: false`, `pipeline-platform: 'github-actions'`, `deploy-option: 'provision-and-deploy'` and present the guidance.

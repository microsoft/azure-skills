# Container Deploy Precheck

Complete every applicable check before running `azd deploy`.

## 1. Select and configure the build path

Follow the existing `docker.remoteBuild` configuration. If it is not set,
default to remote build without asking. Use local build when the user explicitly
requires the image to be built locally.

| Build path | When to use | `azure.yaml` |
|------------|-------------|--------------|
| Remote build | Existing configuration selects it, or no build path is configured | Under the service's `docker` block, set `remoteBuild: true`. |
| Local build | Existing configuration selects it, or the user explicitly requires local build | Under the service's `docker` block, set `remoteBuild: false`. |
| Pre-built image | The user supplies an existing image | Set the service-level `image` to a fully qualified image reference. Under the service's `docker` block, set `imagePassthrough: true` and `remoteBuild: false`. |

## 2. Validate `azure.yaml`

- The intended `azure.ai.agent` service is clearly identified.
- `codeConfiguration:` is absent and `language: docker` is present.
- The selected build path matches the `docker` or `image` configuration.
- Container CPU, memory, and declared protocols are supported.
- `azd env get-values` shows the intended project, model deployment, and ACR.
  For an existing ACR, its name, endpoint, and resource ID identify the same
  registry.

## 3. Validate the container files and code

For remote and local builds:

- The Dockerfile uses the correct build context, copies every required file,
  installs dependencies, and starts the agent server on port 8088.
- `.dockerignore` excludes `.env`, credentials, virtual environments, caches,
  and other local-only files without excluding required application files.
- The entry point and dependency files match the application source.

## 4. Validate the ACR connection

If `azd provision` created or connected the ACR, continue after provision
succeeds. For an existing ACR, verify that the Foundry project has a Container
Registry connection targeting it; otherwise, configure and provision the
connection before deploy.

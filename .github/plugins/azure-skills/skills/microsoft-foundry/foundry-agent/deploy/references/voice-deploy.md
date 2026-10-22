# Voice Agent Deployment

Voice Agents are deployed through `azd`. First read [create-voice](../../create/create-voice.md), [common Voice invariants](../../create/references/voice-agent-common.md), and the selected subtype reference linked from the creation workflow.

## 1. Resolve and Validate

Classify the selected service as Prompt Voice or Hosted Voice. For Hosted Voice, include both the Voice wrapper and its named hosted target in scope.

```bash
azd env get-values
azd ai project show --output json
azd ai agent show --output json
```

## 2. Provision When Required

Respect the project-selection gate: if no Foundry project endpoint is configured and the user has not asked to create one, stop and ask. Run `azd provision --no-prompt` when creating a project or provisioning model deployments or ACR infrastructure.

## 3. Deploy

Prompt Voice:

```bash
azd deploy <voice-service-name> --no-prompt
```

Hosted Voice: deploy the `kind: hosted` target before or together with the `kind: voice` wrapper:

```bash
azd deploy <target-service-name> --no-prompt
azd deploy <wrapper-service-name> --no-prompt
```

Alternatively, run `azd deploy --no-prompt` to deploy all services in dependency order.

## 4. Verify in Two Stages

1. Run `azd ai agent show --output json` and verify status `active` or `deployed`. For Hosted Voice, report the active version of the target and wrapper separately.
2. Do not run `azd ai agent invoke`; it does not support the `voice` protocol. Do not use generic `azd ai agent eval generate` as a Voice smoke test; transcript evaluation has separate limits in [observe](../../observe/observe.md).
3. **Automated technical gate:** run [smoke-test-voice.sh](../../create/scripts/smoke-test-voice.sh) or [smoke-test-voice.ps1](../../create/scripts/smoke-test-voice.ps1). Deployment is technically verified only when the service version(s) are active and this test succeeds.
4. **Manual experience acceptance:** provide the Voice Agent Playground URL from `azd ai agent show --output json` and recommend a complete microphone/audio-to-audio test in the Foundry portal.

Follow [Voice smoke testing](../../create/references/voice-agent-smoke-test.md); do not attribute portal-only experience properties to the automated smoke test.

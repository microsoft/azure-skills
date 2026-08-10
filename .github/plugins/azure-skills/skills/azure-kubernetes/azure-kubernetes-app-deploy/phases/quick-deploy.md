# Quick Deploy

Deploy an application to an existing AKS cluster with production-grade artifacts.

## Section 1: Detection

Scan the project and Azure environment. Ask at most one clarifying question if genuinely ambiguous (multiple Dockerfiles, ACRs, or identities).

### Framework Detection

Follow the framework detection table in `references/detection.md`. Scan for signal files at the project root (and one level deep for monorepos).

### Port and Health Endpoint Detection

Follow the port and health endpoint detection tables in `references/detection.md` (first match wins). If none found, use `/health` as default in probes.

### Existing Artifact Detection

Check for existing `Dockerfile` and `k8s/` (or `manifests/`, `deploy/`) directories.

### Azure Infrastructure Detection

```bash
kubectl config current-context
az aks show -g <rg> -n <cluster> -o json
```

Extract from cluster details:
- **AKS flavor**: `nodeProvisioningProfile.mode` — `"Auto"` = AKS Automatic, otherwise Standard
- **OIDC issuer**: `oidcIssuerProfile.issuerUrl`
- **Azure RBAC**: `aadProfile.enableAzureRBAC`

### Routing Detection

```bash
az aks show -g <rg> -n <cluster> --query '{webAppRoutingEnabled: ingressProfile.webAppRouting.enabled, istioMode: serviceMeshProfile.istio.mode}' -o json
```

- If `webAppRoutingEnabled` is not `true`, stop with error: `az aks approuting enable -g <rg> -n <cluster>`
- If `istioMode` is `"Enabled"` → use **Gateway API** (`gateway.yaml` + `httproute.yaml`, `gatewayClassName: istio`)
- Otherwise → use **Ingress** (`ingress.yaml`, `ingressClassName: webapprouting.kubernetes.azure.com`)

```bash
az acr list -g <rg> -o json
az identity list -g <rg> -o json
```

### ACR-AKS Integration

Verify the AKS kubelet identity can pull images from the detected ACR:

```bash
az aks check-acr --resource-group <rg> --name <cluster> --acr <acr-name>.azurecr.io
```

If the check fails, attach the ACR (requires confirmation): `az aks update -g <rg> -n <cluster> --attach-acr <acr-name>`

If Azure RBAC is enabled, verify namespace create permission: `kubectl auth can-i create namespaces` — if `no`, stop and offer alternatives: have an admin create it, or deploy to an existing namespace.

If any detection command fails, suggest: `az login`, `az account set -s <subscription-id>`, `az aks get-credentials -g <rg> -n <cluster>`.

### Knowledge Pack

After framework detection, load the matching pack from `knowledge-packs/frameworks/` if available (see `SKILL.md`).

Knowledge packs influence Dockerfile optimization, probe configuration, and writable paths.

---

## Section 2: File Generation

Write all files in a single response turn.

### Dockerfile

**If existing Dockerfile:** Validate against best practices (multi-stage build, non-root USER, base tags pinned to a stable major tag (not :latest, not a frozen patch), layer caching, .dockerignore). Apply targeted fixes for failures — do not regenerate the file.

**If no Dockerfile:** Generate from the appropriate template:

| Language | Template |
|----------|----------|
| Node.js | `templates/dockerfiles/node.Dockerfile` |
| Python | `templates/dockerfiles/python.Dockerfile` |
| Java | `templates/dockerfiles/java.Dockerfile` |
| Go | `templates/dockerfiles/go.Dockerfile` |
| .NET | `templates/dockerfiles/dotnet.Dockerfile` |
| Rust | `templates/dockerfiles/rust.Dockerfile` |

**Resolve the base image version.** The templates carry `<LATEST_STABLE_*>`
placeholders. Before writing the Dockerfile, replace each with the current
stable major the project targets, following `references/base-images.md`
(explicit registry/release check; fall back to latest-known with a verify
comment). The generated Dockerfile must end up pinned to a concrete major tag
— this is required for DS009.

Generate `.dockerignore` if missing — use the matching template from `templates/dockerfiles/<language>.dockerignore`.

### Kubernetes Manifests

**If existing manifests found** (in `k8s/`, `manifests/`, or `deploy/`): Validate against AKS Deployment Safeguards (Section 3) and apply targeted fixes. Do not regenerate — improve in place.

**If no manifests found:** Generate from `templates/k8s/` templates. Replace `<angle-bracket>` placeholders with detected values.

| Manifest | Template | Notes |
|----------|----------|-------|
| `k8s/namespace.yaml` | `templates/k8s/namespace.yaml` | |
| `k8s/serviceaccount.yaml` | `templates/k8s/serviceaccount.yaml` | Workload Identity |
| `k8s/deployment.yaml` | `templates/k8s/deployment.yaml` | image tag set after `az acr build`, not at generation time |
| `k8s/service.yaml` | `templates/k8s/service.yaml` | |
| `k8s/gateway.yaml` | `templates/k8s/gateway.yaml` | Istio only |
| `k8s/httproute.yaml` | `templates/k8s/httproute.yaml` | Istio only |
| `k8s/ingress.yaml` | `templates/k8s/ingress.yaml` | Ingress only |
| `k8s/hpa.yaml` | `templates/k8s/hpa.yaml` | min: 2, max: 10 |
| `k8s/pdb.yaml` | `templates/k8s/pdb.yaml` | minAvailable: 1 |
| `k8s/configmap.yaml` | `templates/k8s/configmap.yaml` | If env config needed |
| `k8s/networkpolicy.yaml` | `templates/k8s/networkpolicy.yaml` | Ingress-controller-scoped |

### Hostname

Omit the `host` field from Ingress `rules` (or Gateway `listeners`) for initial deployments — traffic routes to the external IP directly. Add `host` and TLS once the user has a domain.

### Resource Sizing

Use the framework-specific defaults from the knowledge pack's "Resource Sizing" section. If no pack is loaded, use `requests: {cpu: 100m, memory: 128Mi}` and `limits: {cpu: 500m, memory: 256Mi}`.

### Startup Probe

For slow-start frameworks (Java/Spring Boot, .NET with heavy DI), uncomment `startupProbe` in the deployment template to prevent liveness restarts during init.

---

## Section 3: Safeguards Validation

Validate all generated manifests against DS001-DS013 (reference `references/safeguards.md`).

- 12 of 13 rules are auto-fixable. DS009 (no `:latest` tag) is resolved by tagging with git SHA.
- Apply the writable paths from the loaded pack (for `readOnlyRootFilesystem: true` compliance with DS012).
- Reference `references/workload-identity.md` for Workload Identity configuration.

**AKS Automatic:** all violations must be fixed.

**AKS Standard:** check `safeguardsProfile.level`:
```bash
az aks show -g <rg> -n <cluster> --query 'safeguardsProfile.level' -o tsv
```
- `Enforcement`: fix all violations
- `Warning` or `Off`: warn, don't block

---

## Section 4: Deploy

### Ensure kubectl context

```bash
az aks get-credentials -g <resource_group> -n <aks_cluster_name> --overwrite-existing
```

### Verify Gateway API CRDs (only if Istio Gateway API detected)

```bash
kubectl get crd gateways.gateway.networking.k8s.io httproutes.gateway.networking.k8s.io 2>/dev/null
```

If missing: `kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/latest/download/standard-install.yaml`

### Build and push

```bash
IMAGE_TAG=$(git rev-parse --short HEAD)   # fallback: date +%Y%m%d%H%M%S
az acr build --registry <acr_name> --image <app-name>:$IMAGE_TAG --file Dockerfile .
```

**Monorepo:** Adjust `--file` and context to the app subdirectory (e.g., `--file apps/myapp/Dockerfile apps/myapp/`).

### Deploy to cluster

```bash
# 1. Create namespace (must succeed before proceeding)
kubectl apply -f k8s/namespace.yaml
kubectl get namespace <namespace> -o name   # verify

# 2. Apply remaining manifests
kubectl apply -f k8s/ --recursive

# 3. Wait for rollout
kubectl rollout status deployment/<app-name> -n <namespace> --timeout=300s
```

If any step fails, show the error and stop. See `references/rollback.md` for recovery.

---

## Section 5: Verify

```bash
kubectl get pods -n <namespace> -l app=<app-name>
kubectl get gateway -n <namespace> -o jsonpath='{.items[0].status.addresses[0].value}'  # if Gateway API
kubectl get ingress -n <namespace> -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}'  # if Ingress
```

Wait up to 3 minutes for external IP, then curl the health endpoint.

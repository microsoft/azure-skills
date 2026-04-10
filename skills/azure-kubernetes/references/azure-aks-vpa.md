# AKS Vertical Pod Autoscaler (VPA)

Use VPA to get data-driven resource recommendations for rightsizing pods. Always start in recommendation-only mode before considering auto-apply.

## Enable VPA (Recommendation Mode)

```bash
# Install VPA (if not present)
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/latest/download/vertical-pod-autoscaler.yaml

# Create a VPA object in recommendation mode for a deployment
kubectl apply -f - <<EOF
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: <DEPLOYMENT_NAME>-vpa
  namespace: <NAMESPACE>
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: <DEPLOYMENT_NAME>
  updatePolicy:
    updateMode: "Off"   # Recommendation only — does not modify pods
EOF

# Read recommendations after 24+ hours of data collection
kubectl describe vpa <DEPLOYMENT_NAME>-vpa -n <NAMESPACE>
```

> Risk: Low in "Off" mode. **Do not use `updateMode: Auto` in production** without thorough testing and explicit user confirmation.

## Read VPA Recommendations

```bash
kubectl get vpa <DEPLOYMENT_NAME>-vpa -n <NAMESPACE> -o jsonpath='{.status.recommendation}'
```

The output shows `lowerBound`, `target`, and `upperBound` for CPU and memory. Use the `target` values as rightsized requests.

## Apply Recommendations Manually

After reviewing VPA output, patch the deployment — see [azure-aks-rightsizing.md](./azure-aks-rightsizing.md#yaml-patch-format) for the patch format.

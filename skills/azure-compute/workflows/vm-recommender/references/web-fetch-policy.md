# web_fetch policy

Steps 2 and 3 of the recommender rely on `web_fetch` against `learn.microsoft.com` to verify that a recommendation reflects current capabilities (especially VMSS features, family availability, and Spot eligibility).

## When `web_fetch` succeeds

Use the live documentation as the source of truth. Cite the URL in the recommendation so the user can verify.

## When `web_fetch` fails (timeout, 404, blocked, offline)

Proceed using the reference files in `../../references/` — but **always** include this warning in the recommendation:

> ⚠ Unable to verify against latest Azure documentation. Recommendation is based on reference material that may not reflect recent updates (e.g., new VM families, Spot eligibility changes, regional rollouts).

Do not block the recommendation on `web_fetch` failure. The user is better served by an annotated recommendation than by no recommendation.

## What to fetch (Step 2 — VMSS)

```
https://learn.microsoft.com/azure/virtual-machine-scale-sets/overview
https://learn.microsoft.com/azure/virtual-machine-scale-sets/virtual-machine-scale-sets-autoscale-overview
```

## What to fetch (Step 3 — VM family)

```
https://learn.microsoft.com/azure/virtual-machines/sizes/<family-category>/<series-name>
```

Examples:
- B-series: `https://learn.microsoft.com/azure/virtual-machines/sizes/general-purpose/b-family`
- D-series: `https://learn.microsoft.com/azure/virtual-machines/sizes/general-purpose/ddsv5-series`
- GPU: `https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/nc-family`

For Spot, also: `https://learn.microsoft.com/azure/virtual-machine-scale-sets/use-spot`.

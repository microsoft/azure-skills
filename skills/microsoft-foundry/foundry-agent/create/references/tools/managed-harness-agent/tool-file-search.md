# File Search

File Search requires an existing vector store:

```yaml
tools:
  - type: file_search
    vector_store_ids:
      - <vector-store-id>
    max_num_results: 10
    ranking_options:
      ranker: auto
      score_threshold: 0.5
```

Do not invent or create a vector store as part of this Phase 1 workflow. If the user did not provide an ID and the existing Managed Harness Agent does not reference one, stop and request it.

azd passes nested `ranking_options` and `filters` to Foundry without complete validation.

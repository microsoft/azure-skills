## Interfaces and versions

| Operation | Contract |
|---|---|
| Search substrate management | management API `2025-05-01` |
| Resource group prerequisite | ARM `2022-09-01` |
| AI account | ARM `2025-06-01`; File CU GET/listKeys `2024-10-01` |
| Search data plane | Entra audience `https://search.azure.com/.default` |
| File knowledge source and file operations | `2026-08-01-preview` |
| Blob knowledge source | GA `2026-04-01`; preview for selected preview features |
| ADLS Gen2 knowledge source | This helper uses `2026-08-01-preview` |
| Existing Blob validation | Entra audience `https://storage.azure.com/.default`; Blob `x-ms-version: 2025-11-05` |
| Existing Prompt Agent connection | authenticated Foundry MCP preferred; `azure-ai-projects>=2.4.0,<3` typed fallback; Agent API `v1`; project-connection ARM API `2025-10-01-preview`; KB MCP endpoint `2026-08-01-preview` |
| Existing Hosted Agent connection | GET-only toolbox assessment; source-backed azd recipe; `AgenticIdentityToken`; KB MCP `2026-08-01-preview` |

Execution surfaces:

| Workflow | Surface |
|---|---|
| Missing group/Search/models/RBAC | Conditional `references/bootstrap-azure.md`: native Azure CLI/ARM; no host fixture |
| File read-only plan / approved source plus upload | `helpers/file_source.py --plan request.json` / `--input approved-envelope.json` |
| Blob/ADLS read-only plan / approved application | `helpers/blob_source.py --plan intent.json` / `--input approved.json` |
| Source vector verification plan / separately approved query | `helpers/source_vector.py --plan verify.json` / `--input approved-query.json`; [contract](../helpers/vector-contracts.md) |
| Knowledge-base reconciliation / source or KB cleanup | `helpers/search_reconcile.py` |
| Existing Prompt fallback connect/delete | `helpers/prompt_connect.py` / `helpers/prompt_cleanup.py` |
| Hosted assessment / source-backed connection | `helpers/hosted_connect.py --plan intent.json` / `agents/connect-hosted.md` |

Receipts preserve the first nonempty case-insensitive value for
`x-ms-request-id` or Azure Search's `request-id`, preferring the former when
both are present. Client-generated/echoed request IDs are not server provenance; missing server IDs remain missing.

Standalone retrieval uses Entra-authenticated Search REST:
GET `/knowledgebases('<escaped-name>')?api-version=<version>`, then
POST `/knowledgebases/<name>/retrieve?api-version=<version>`.
GA and preview minimal use `intents`; preview low/medium can use `messages`.
Read the selected definition and preserve its API/mode/effort. See
[Retrieve](../knowledge-bases/retrieve.md) for request construction, permission
forwarding and response verification. No MCP connection is required.

Prompt/Hosted Agent connections still use the exact KB's native MCP endpoint
(`/knowledgebases/<knowledge-base>/mcp?api-version=<api-version>`) and
`knowledge_base_retrieve`. REST retrieval is not proof of agent tool use.
Neither path substitutes the generic Azure MCP Server `search_*` group or an
index query. Preserve first errors; never persist tokens or use Search/Storage keys.

### Hosted connection readback

An `azd` projection may omit audience; a typed MCP reader may return
`UnknownConnectionPropertiesV2` for `AgenticIdentityToken`. For those schema
gaps, read the observed `Microsoft.CognitiveServices/accounts/projects/connections`
resource ID without fetching credentials:

```text
az resource show --ids <exact-connection-resource-id> --api-version 2025-10-01-preview --query "{id:id,category:properties.category,authType:properties.authType,target:properties.target,audience:properties.audience}" --output json
```

Require the approved ID, `RemoteTool`, `AgenticIdentityToken`, KB MCP target and
`https://search.azure.com/` audience. Compare other protected fields when needed.
Never use `--show-credentials`, keys or secret endpoints. This supported ARM GET
is diagnostic readback, not an alternative mutation surface or an authorization
bypass. Denial, mismatch or missing required fields still blocks.

### API selection

| Request | Service availability and helper choice |
|---|---|
| File non-image minimal | Service: `2026-05-01-preview`/`2026-08-01-preview`; helper August (multipart metadata, 200 files) |
| File CU or images | `2026-08-01-preview`, `standard`; planner and executor supported. May rejects images; minimal returns 415 in both. CU is independent of source vectors |
| Blob minimal or standard CU | `2026-04-01` GA unless a selected feature requires preview; CU alone does not force preview |
| ADLS in this helper | `2026-08-01-preview`; do not describe a helper restriction as a platform prohibition |
| Permission/private ingestion | Preview properties require `2026-08-01-preview`; this source planner does not implement either, schedules or user-assigned identities |
| KB low/medium, synthesis or agent connection | Explicit preview configuration; GA helper is minimal/extractive. KB models and source embeddings/CU are separate |

File `--plan` optional `api_version` defaults to August; unsupported:
compatible-client handoff, never silent upgrade.
Choose source/KB APIs separately; no GA preview fields, silent downgrade,
unsupported helper features or skillset edits.

### Source formats

Admission is not content fit: owners assess structure/answer needs.

The File service detects content type; MIME cannot override it. Minimal accepts
PDF, DOC/DOCX, PPT/PPTX, XLS/XLSX, JSON, shell scripts and detected `text/*`,
including TXT/MD/HTML/CSV. The helper preserves bytes and deterministic filename
hints, not detected types. Unknown/extensionless files use `application/octet-stream`.
Search-detected images need August standard; hints cannot require CU or block minimal.

Upload only selected paths; never execute scripts, unpack archives or auto-include
hidden files. Credential targets, including selected root components, are blocked;
this is not a secret scan. Preserve tier/count/root/link
guards and historical artifact bytes/MIME/fingerprints. Server 415 stops ingestion,
retaining earlier writes/source ownership and first failure; never completed.

Blob indexer formats apply to Blob/ADLS knowledge sources: CSV, EML, EPUB, GZ, HTML, JSON, KML, MD,
DOC/DOCX/DOCM, XLS/XLSX/XLSM, PPT/PPTX/PPTM, MSG, Word XML 2003/2006,
ODT/ODS/ODP, PDF, plain text, RTF, XML and ZIP. Generic Storage MIME is not
grounds for rejection. Compound/archives are one blob document before chunking,
not one KB document per entry. Never unpack/upload/modify blobs or widen scope.
Require successful ingestion, not just source acceptance.

CU skill formats are PDF, JPEG/JPG, PNG, BMP, HEIF, TIFF, DOCX, XLSX, PPTX, HTML, TXT, MD, RTF,
EML. Blob indexer acceptance does not prove CU support for ZIP/legacy Office.
Both limits apply, including the five-minute CU timeout; no universal support.
File follows its detected-type contract, not this Blob CU list.
CU image descriptions/semantic chunking: preview since `2026-05-01-preview`;
not exposed by this planner.

## Sources

Authorities: failure/conflict/uncertainty only.

[File](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file#file-support-and-limits),
[Blob indexer](https://learn.microsoft.com/azure/search/search-how-to-index-azure-blob-storage#supported-document-formats),
[CU skill](https://learn.microsoft.com/azure/search/cognitive-search-skill-content-understanding#supported-file-formats).
Schemas: [RG](https://github.com/Azure/azure-rest-api-specs/blob/main/specification/resources/resource-manager/Microsoft.Resources/resources/stable/2022-09-01/resources.json),
[AI ARM](https://github.com/Azure/azure-rest-api-specs/blob/main/specification/cognitiveservices/resource-manager/Microsoft.CognitiveServices/stable/2025-06-01/cognitiveservices.json).
[Scope](https://learn.microsoft.com/azure/governance/policy/concepts/scope)
and [assignments](https://learn.microsoft.com/azure/governance/policy/concepts/assignment-structure).

# Content-fit intake for ingestion

Read when File or Blob/ADLS content/answer needs are unknown or a mode conflicts
with the goal, even if a processing mode was explicitly named.
Honor explicit processing choices only when informed and compatible with the
confirmed outcome; reuse known content descriptions and answer needs without
asking again. Explain a known mismatch and clarify before planning: never
override the choice or silently reduce the requested outcome.
Unknown content requires assessment before a recommendation, even if the user
already confirmed a technical plan. Neither suffix/MIME nor inventory metadata
establishes suitability; service-detected file type remains admission authority.

Text-only can use hybrid; multimodal can use keyword-only.

## Explicit choice checks

| Request | Before planning |
|---|---|
| Minimal; unknown PDF content | Assess via consented samples or questions. |
| Minimal; visual answers needed | Clarify supported outcome, no silent omissions/override. |
| Informed text-only reduced outcome | Preserve exclusions/admission checks; do not reask. |
| Use Standard to interpret trends in charts. | Planner verbalization is off: disclose limits; explicit supported reduced outcome or handoff, no flag/model escalation. |

## Two routes, not a file-sharing requirement

Offer: "I can inspect a few representative samples you authorize, or you can
describe the content."

Primary question: "Are these documents text-only, or do they contain multimodal
content such as images, charts, diagrams, tables or meaningful page layout?"
Options: **text-only / multimodal / mixed-or-unsure**. For mixed-or-unsure,
offer authorized inspection or questions, never require file sharing.
A born-digital/searchable PDF is **not synonymous with text-only**.
Searchable text may coexist with answer-critical visual/layout information.

Only if answer dependence is not already known, ask separately: "Do the answers
you need depend on visual or layout information, rather than text alone?"
Use answer-dependence labels **text alone**, **OCR + table/layout relationships**,
or **chart/diagram/image interpretation (verbalization off in this planner profile)**.
Reuse informed answers; do not repeat this question.
Scans are one example of image-based content, not the primary taxonomy.
OCR/searchable-text availability is a secondary conditional follow-up only when
needed to resolve extraction suitability, not the opening content question.

- **Description:** a useful answer is sufficient; do not force files or repeat
  answered questions. Ask only unresolved figure/table answer needs.
  A searchable PDF can still need visual extraction.
- **Samples:** agree exact local paths, file/page count, byte/output limits,
  inspection purpose and permitted content exposure first. Use only available,
  supported local read-only viewers/parsers. **Only when document inspection is selected**,
  read [bounded document assessment](../helpers/document-assessment.md): declared
  adapters, exact scope/hash, whole-file metadata consent, time/memory limits and
  counts only; no text viewer on PDF binary. Dependency installation needs separate
  approval, never ad-hoc tooling. Never execute scripts/macros, extract
  archives to disk or follow links. Other approved text samples need host-appropriate
  quoting and byte/output bounds; line count alone is not a byte bound.
  If no safe supported viewer can inspect the needed structure, use the description route.
  For Blob/ADLS ask for customer-provided local representative copies; do not
  download blobs to decide. Never scan/download an entire container or widen
  the selected root/prefix. Metadata discovery is not content inspection consent.
  Never upload samples to CU, embeddings or chat-model services just to choose.
  Do not retain raw sample content in plans, logs or summaries.
- **Mixed content:** cover each relevant content family and answer-critical
  structure, not just the first/easiest text file. Ask how representative the
  samples are; describe uninspected portions and uncertainty. A small sample is
  not corpus-wide extraction proof.
- **Inspection unavailable, declined or unreadable:** ask whether content is
  **text-only / multimodal / mixed-or-unsure**, not searchable versus scanned.
  Only if unknown, ask separately whether answers need text alone,
  **OCR + table/layout relationships**, or **chart/diagram/image interpretation
  (verbalization off in this planner profile)**. Reuse informed answers; no inspection/upload
  is required. Never infer text-only from failure, refusal or no samples.
  If content/answer needs remain unknown, leave processing unresolved and pause
  source planning; no automatic Minimal or forced file sharing.

## Recommend, then approve

| Capability | Minimal | Standard: typed File/Blob |
|---|---|---|
| Basic text/existing text captions | Supported text, not image interpretation | Text extraction |
| Layout/tables | Relationships surviving text | CU layout to Markdown; imperfect |
| OCR | Not added | CU-supported; no accuracy guarantee |
| AI-generated image captions | Off | Off; broader CU supports descriptions with ingestion chat |
| Chart/diagram interpretation | Not promised | Not promised; reduced outcome/handoff |

Input profile (text-only/multimodal/unknown) differs from indexed Markdown.
Text output cannot prove text-only input; counts do not select a mode.

Recommend **Minimal** when supported searchable text supplies the needed answers,
including ordinary text tables whose relationships survive text extraction.
Minimal avoids additional CU cost, dependencies and processing latency;
Search/ingestion and selected embeddings still cost.

Recommend **Standard (Content Understanding)** for answer-critical OCR or
table/layout relationships that the selected operation may support, subject to
supported formats and the source-specific recipe. It already extracts structured
Markdown/text chunks; no generated `.md` file or perfect table/chart extraction
is promised. Explain billable CU, potentially higher
processing latency, required region/configuration/access, data movement and
retention. Standard is not universally better; images/tables/extensions alone do
not select it. No timing/quality guarantee.

Label **Standard: OCR/layout to Markdown; image descriptions off in this planner
profile**. These typed planners set `disableImageVerbalization: true` and omit
`chatCompletionModel`; this is not
a CU service-wide limitation. Optional image descriptions also yield text, but
need an ingestion chat-model purpose, not necessarily a new deployment.
Source embeddings and KB synthesis chat remain separate. Multimodal input alone
requires neither verbalization nor KB chat. For unsupported visual answer needs,
clarify a supported outcome or handoff; no hidden model calls.
Never automatically enable image verbalization or add/escalate a chat model.

State the observed or customer-described basis, coverage/uncertainty, recommended
mode and tradeoff in user terms; retain that rationale with the workflow handoff,
not a fabricated helper evidence boolean. Ask only the unresolved mode decision.
Cost refusal, denied permissions or unavailable CU blocks that choice; explain
limitations and alternatives, but never silently downgrade. A customer may
explicitly choose a supported reduced outcome after learning its limitations.

Selection and sample consent are not ingestion/dependency consent. Return to the
source owner's concrete-plan approval and applicable CU/data-movement approvals
before writes; never auto-provision CU, change local auth, enable preview or widen
data boundaries. File standard uses verified MI or approved keys/August preview;
Blob CU uses existing keyless dependencies/GA or selected preview, ADLS preview.
Do not transplant recipes. Extraction is independent of lexical/vector indexing,
KB reasoning/synthesis and agent models; no model calls to make this decision.

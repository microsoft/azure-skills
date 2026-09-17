# Bounded document assessment

Read **only when document sample inspection is selected** from content-fit intake.
Structural facts only; no conversion or admission proof.
Refusal remains valid. No upload, OCR, rasterization, model call,
macro/script/formula execution, external URI/object resolution or file extraction
to disk. Never inspect binary documents using text viewers.

## Exact approval and read contract

Before any read, approve exact local file/SHA-256/scope/ceilings. Separately approve
whole-file hashing if identity is unknown. No inspection/hash/worker on decline.
One file/invocation; no automatic batches, retries, wider scope or larger limits.

PDF: explicit 1-based pages, maximum eight selected pages/200 total pages.
Others require `--whole-document`, not guessed page subsets; narrower non-PDF
scope is unsupported. Pagination/rendering is not assessed.
Whole-file hashing and PDF trailer/xref/object-stream/page-tree parsing remain
necessary; compressed containers may include unselected objects. Only selected
PDF streams are assessed, never other pages to guess modality. Decline if this
whole-file structural metadata parsing is unwanted.

Use a customer-controlled private local scope. No URLs, device/UNC/mapped-network
paths, symlinks/reparse points or untrusted writable directories. Linux mount
locality and concurrent file replacement remain operator responsibilities.
Blob/ADLS: reuse customer-provided, separately authorized local sample copies.
This tool implements **no remote read/download adapter**. Remote requests return
`remote-sample-access-not-supported`, not a container/subscription crawl.
Separate sample-access approval names exact account/container/blob/version/ETag,
byte range/full-file read, destination, retention and limits. Local path/hash
approval remains required; no remote provenance verification or wider prefix.

```text
python "<skill-root>\helpers\document_assess.py" --approve-inspection --file "C:\approved\sample.pdf" --sha256 <64-lowercase-hex> --pages 1,3
python "<skill-root>\helpers\document_assess.py" --approve-inspection --file "C:\approved\sample.docx" --sha256 <64-lowercase-hex> --whole-document
```

POSIX: native paths/quoting. Optional `--format`:
`auto`, `pdf`, `text`, `markdown`, `html`, `json`, `docx`, `pptx`, `xlsx`, `png`,
`jpeg`. Byte signatures/OOXML content types determine binary adapters, never
extensions/MIME. Text auto mode reports UTF-8 text; HTML/JSON need explicit hints for structure,
Markdown for lexical counts. Hints cannot override binary detection, ingestion
mode or Search server admission. Auto-detected PDF still needs exact pages.

## Declared installation and limits

Python 3.11+, Windows/Linux. Separately approve installation outside inspection;
no automatic install or library guessing:

```text
python -m pip install -r "<skill-root>\helpers\requirements-assessment.txt"
```

`pypdf==6.8.0` (BSD-3-Clause): PDF; `defusedxml==0.7.1` (PSF license): Office XML;
others use stdlib. Missing/wrong selected-adapter versions block, without
affecting other adapters. Nothing vendored; MIT-compatible distribution requires
retaining dependency notices/non-endorsement terms when bundling.
Repository development: `uv sync --locked` (`pyproject.toml`/`uv.lock`).

| Bound | Fixed ceiling |
|---|---|
| File / worker / output | 16 MiB input; 256 MiB worker; 10 CPU seconds; 15 seconds wall including startup/read; 8 KiB JSON |
| Text / HTML / JSON | 2 MiB UTF-8 input; JSON depth 64/100,000 nodes; HTML 100,000 start tags |
| Office ZIP/XML | 256 entries; 2 MiB per inflated entry; 16 MiB aggregate declared inflation; compression ratio 100; 100,000 inspected XML nodes/depth 64 |
| Images | PNG IHDR/JPEG SOF0/1/2 headers only; 100 million declared pixels; 4,096 JPEG markers; no pixel decompression |

ZIP: stored/deflated only; encrypted/macro packages, duplicate/unsafe paths and
inflation excess block. Capped in-memory reads, no disk extraction. XML forbids
DTDs/entities/external references. OS limits cover forged sizes, decompression,
cycles and allocations before post-parse node checks.

Windows Job Object: process commit-memory/CPU/active-process limits. Linux:
`RLIMIT_AS`/`RLIMIT_CPU`, zero core/file-output limits; not RSS quotas.
Install before source reads/parser imports or block. Parent timeout/output guards
kill only their owned PID. Audit denies writes/network/processes; after trusted
parser/codec imports, file/directory reads too. Unsupported lazy features block.
This is **not an OS security sandbox or proof against every hostile document**.
OS paging/crash dumps remain outside the helper's privacy boundary.

## Fact semantics and coverage

| Adapter | Reported structural facts; exclusions |
|---|---|
| PDF | Page-tree count; selected-page Unicode length/nonempty flag; direct image/path paint and Form calls. Not unique/visible images, lines or tables. Forms untraversed/their text unassessed; total images/drawings unknown. |
| Text/Markdown | UTF-8 character count including whitespace/markup, not an AST or visual classification. Other encodings unassessed. |
| HTML | Data-event characters excluding script/style; recognized img/table/tr/td/th tag counts. Tolerant syntax, not rendering, table relationships or fetched images. |
| JSON | String-value characters, object/array/key counts, not keys' contents, schema semantics or numeric text interpretation. |
| DOCX | Main-document text/paragraph/table/blip elements; headers/footers/notes/embedded objects unassessed. |
| PPTX | Standard numbered slide parts' text/paragraph/table/blip elements and part count; not order, notes, diagrams or linked objects. |
| XLSX | Standard worksheet/shared-string/table parts: stored text, formula/cell/table counts, declared sheets. Shared strings counted once, not cell occurrences; no evaluation/numeric/chart interpretation. |
| PNG/JPEG | Dimensions/numeric headers; PNG IHDR CRC checked. Pixels, orientation, further frames and completeness unassessed. |

Office: conventional transitional namespaces/parts only. Unreferenced standard
slide/sheet parts may be counted; relationships unresolved. Image references/
table elements prove neither visibility, preserved relationships nor semantics.
Every report keeps input profile `unknown`, OCR need/answerability/layout
relationships `not-assessed`. `not-applicable` distinguishes non-page formats or
irrelevant typed counters; unknown facts never become false zero counts.
Text output/Markdown representation cannot prove text-only input or choose CU.

## Return and fallback

Exit `0`/`completed`, `assessment: assessed`: adapter facts only.
Exit `2`/`blocked`, `assessment: not-assessed`, `facts: null`: approval/scope/identity/
limits, malformed/encrypted/unsupported content, missing adapter, warning or
worker failure. Do not invent worker-death causes. Legacy Office, other formats
and unsupported profiles are unassessed—not rejected for service ingestion.
All reports say `service_admission: not-assessed`; preserve the blocker and use
description/answer questions, never assume text-only or silently downgrade.

After identity verification, bind source SHA-256 and canonical path SHA-256
(UTF-8 absolute path, Windows case-normalized). Changed bytes block before parsing;
original File bytes remain unchanged.
No raw text/keys/snippets/images/drawing operands/archive names in stdout/stderr/
artifacts. Only aggregate JSON leaves worker memory; no temporary files/deletion.
Return coverage/uncertainty to content-fit, then source-owner plan/ingestion
approvals—not fabricated evidence.

Authorities: failure/conflict/uncertainty only.
- [pypdf contract/license](https://pypi.org/project/pypdf/6.8.0/)
- [XML parser/license](https://github.com/tiran/defusedxml)
- [OOXML](https://ecma-international.org/publications-and-standards/standards/ecma-376/)
- [PNG specification](https://www.w3.org/TR/png-3/)
- [JPEG T.81](https://www.itu.int/rec/T-REC-T.81)

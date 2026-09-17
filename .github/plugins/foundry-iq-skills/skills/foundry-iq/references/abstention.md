# Unsupported-answer audits

For synthesis, judge semantic abstention, not a fixed phrase, only after a successful
retrieval with no service/activity errors. Clear no-support statements qualify, such
as `I don't know`, `No relevant content was found for your query`, or
`The sources do not specify that information`. These are examples, not an exhaustive
phrase allowlist.

Assess the complete answer: reject invented facts and misleading answer citations.
A caveat does not cancel an unsupported assertion, such as turning a response target
into a resolution guarantee. Unused entries in `references` are not answer citations;
check the references actually used to support answer claims. Access denials, timeouts,
partial responses and tool failures are not abstention.

Honor any explicit exact-output contract required by the user or configured KB/agent.
Report semantic abstention and exact-format compliance separately; semantic success
does not override a format failure. Never rewrite returned answers or retroactively
change historical verdicts.

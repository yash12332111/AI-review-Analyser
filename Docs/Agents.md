# Project Rules — Spotify Review Analyser

## Source of truth
The implementation_plan.md and Architecture.md are the source of truth. Do not
deviate from them without flagging it explicitly and asking first. If you change
a documented decision, say so clearly — never change it silently.

## Schema discipline (critical)
The classification schema is exactly 11 fields as defined in the Pydantic model
in implementation_plan.md: topic, core_complaint, trust_level, sentiment,
frustration_intensity, user_job_to_be_done, repeat_listen_reason,
workaround_mentioned, workaround_description, behaviour_pattern, pattern_evidence
(plus unmet_need where the plan specifies it). Do NOT add, rename, or drop fields.
Do not invent fields like churn_risk. Use the plan's Pydantic model verbatim.

## Open-extraction guardrails (do not violate)
1. In the classifier prompt (prompts.py), always keep the instruction: "Do NOT
   sort reviews into predefined categories. Describe what is actually in the text.
   Return null when not present." Never replace open-text fields with fixed
   dropdown/enum categories.
2. In the clustering engine (Phase 4.5), never hardcode expected segments,
   frustration categories, or theme lists. Clusters must emerge from the data via
   HDBSCAN. The test_no_hardcoded_categories test must exist and pass — do not
   skip or weaken it.
These two rules are the core of the project's research credibility. If you find
yourself writing a fixed category list, stop.

## Don't paper over failures
If a data source, library, or API fails (e.g. the App Store scraper), do NOT
silently swap it for something else and report success. Flag the failure, explain
it, and ask how to proceed. A working App Store collector is required, not
optional.

## Additions only — don't rewrite existing work
When adding a feature or phase, do NOT remove, rewrite, or restructure existing
working code, phases, tasks, or schema fields unless explicitly asked to.
Additions only. If a change requires modifying something existing, flag exactly
what and why before doing it, and confirm no existing functionality was deleted.
When done, explicitly state what you added and confirm nothing existing was
removed.

## Verify your own changes
After any edit, verify the change actually saved — re-read the file or run a grep
— and show proof. Do not report success based on your plan or intention alone;
confirm against the actual file contents. If asked to remove references to
something, grep for them afterward and report the count to prove they're gone.

## Build discipline
Build one phase at a time. Stop at each phase boundary and run that phase's
acceptance check before moving on. Do not build multiple phases in one pass.
After changes, summarise exactly what you touched.

## Compliant sources only
The data sources are App Store (multi-country), Play Store (multi-country),
Spotify Community, and Trustpilot. Reddit, YouTube, and Quora were deliberately
removed for compliance reasons. Do not re-add them or build scraping workarounds
for blocked sources. If a source needs credentials or approval we don't have,
flag it and ask — don't engineer around it.

## Multi-language data handling (we now have non-English reviews)
The corpus contains reviews in Hindi, Portuguese, and German (Play Store
multi-country), not just English. This affects later phases:

- **Phase 3 (Classification):** Verify non-English reviews classify sensibly,
  not garbled. After building, run a few Hindi, Portuguese, and German reviews
  through the classifier and eyeball the topic/core_complaint/unmet_need
  extractions. If they come back broken or empty, add a translate-then-classify
  step. Acceptance check must include: non-English reviews produce coherent
  English-language extractions.
- **Phase 4.5 (Clustering):** Confirm the embedding model is multilingual so
  reviews cluster by MEANING, not by language. A Hindi complaint about repetition
  and an English one must land in the same cluster. Risk: if the embedding model
  isn't cross-lingual, German reviews form a "German cluster" by language rather
  than theme — a false pattern. Verify cross-language reviews with the same theme
  cluster together before trusting the output.
  ## Source health is measured by DATA, not by "pipeline didn't crash"
A collector that gracefully returns 0 reviews is still a broken collector.
Acceptance for any collection or pipeline phase = real records actually fetched
from each working source, with correct tags (country, source), verified by
querying the database — not just "tests passed" or "ran without error." Graceful
failure handling is good, but it must not mask a source that silently collects
nothing.

## Environment note
The environment runs Python 3.9, not 3.10+. Some libraries (HDBSCAN, ChromaDB)
prefer 3.10+. If a later phase hits an install or import error, check Python
version compatibility first. Use Optional[] / Union[] typing syntax and
`from __future__ import annotations`, not 3.10+ pipe syntax.

## Trustpilot is optional and blocked
Trustpilot returns 403 (active anti-bot blocking) even with browser headers.
This is accepted — do not spend effort trying to defeat their bot protection.
It stays as a graceful, optional source. The working sources are App Store,
Play Store, and Spotify Community.

## Rate limits = throughput, solved by batching + delta processing
Handle Groq rate limits by: (1) only classifying NEW/unclassified reviews each
run, never re-classifying the whole corpus; (2) batching in small chunks across
time to stay under per-minute and per-day token caps; (3) resuming the next day
if the daily cap is hit. Never downgrade the model to avoid limits. Paid Groq
tier is an option if higher throughput is needed, but batching on the free tier
is sufficient for this project's volume.
## Model choice is a quality decision, not a convenience one
GROQ_MODEL is llama-3.3-70b-versatile by design — classification quality is the
research quality this project is scored on. Do NOT silently downgrade to a smaller
model (e.g. llama-3.1-8b-instant) to avoid rate limits. Rate limits are a
throughput problem — solve them with batching over time, not by shrinking the
model. If a model change is genuinely needed, flag it explicitly and show a
quality comparison before switching.

## See quality before accepting a tradeoff
When a change trades quality for convenience (model size, batch shortcuts,
skipping a verification), do not accept it on assertion. Show a concrete
before/after comparison on real data so the quality impact is visible, then
decide. "It works" is not the same as "it works as well."
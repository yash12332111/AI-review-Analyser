Here it is:

---

## Problem Statement

**AI-Powered User Feedback Intelligence System for Music Discovery**

---

### The Problem

Product managers working on consumer music products like Spotify face a fundamental research gap: they can see what users do through internal engagement metrics, but they cannot understand why users behave that way at scale.

Internal data shows repeat listening dominates the platform — users playing the same playlists, the same artists, the same tracks. But internal metrics cannot answer the questions that actually drive product decisions: why do users who want to discover new music end up stuck in comfort loops? What specific moments cause them to abandon discovery and retreat to the familiar? What workarounds have users built because the product failed them? Which user segments experience discovery differently, and what are the unmet needs behind their behavior?

The answers to these questions exist — users are articulating them every day across App Store reviews, Play Store ratings, Spotify Community forums, and Trustpilot. But this feedback is scattered across platforms, unstructured, and impossible to analyze manually at any useful scale.

Current approaches to understanding this feedback fail in four specific ways:

**Single-source, static snapshots.** A PM reads 50 App Store reviews before a sprint planning session and calls it user research. The sample is tiny, the source is one platform out of six, and the insights are already stale by the time they reach a decision.

**Shallow sentiment classification.** Existing review analysis tools tell you a review is "positive" or "negative." They cannot tell you the user is a Frustrated Explorer who built a private workaround playlist because Discover Weekly stopped surfacing anything outside their existing taste profile — or that a Comfort Looper doesn't actually prefer familiar music, they just experience too much decision fatigue to try something new.

**No behavioral depth.** No existing tool classifies reviews across dimensions like discovery barriers, listening intent, repeat-listen triggers, trust levels, or user jobs-to-be-done. Without this depth, product teams are making decisions about discovery features without understanding the psychological and contextual reasons behind user behavior.

**Not queryable, not current.** Even when qualitative research exists, it sits in a static document, out of date within weeks. There is no way for a PM to ask "what do power curators say specifically about mood-based recommendations this week?" and get a sourced, up-to-date answer.

---

### What We're Building

A multi-source, live AI feedback intelligence system that:

**Collects** public user feedback about Spotify's discovery experience from four sources — App Store (multi-country), Play Store (multi-country), Spotify Community, and Trustpilot.

**Refreshes on schedule while the server is running** — the nightly pipeline runs via APScheduler (in-process, requires an active server). It pulls only new feedback since the last run (capped at 200 records per source per run), stores it in a local SQLite database without reprocessing existing records, and generates a delta summary of which patterns are growing or fading (only for categories with 10+ records, to avoid noisy small-sample trends).

**Classifies every piece of feedback across 12 behavioral and psychological dimensions** using the Groq API (Llama 3.3 70B), capped at 900 classifications per run to stay within the free tier, designed to answer six core product questions:

*Why do users struggle to discover new music?*
- `topic` — what the review is generally about (in the model's own words)
- `core_complaint` — the specific barrier or frustration they hit (in the model's own words, or null if positive)
- `trust_level` — how much the user trusts Spotify's recommendations (high / medium / low / broken)

*What are the most common frustrations with recommendations?*
- `frustration_intensity` — mild / moderate / severe / churned
- `sentiment` — overall tone of the review (positive / negative / mixed / neutral)

*What listening behaviors are users trying to achieve?*
- `user_job_to_be_done` — framed as "The user wants to [GOAL] in [CONTEXT] without [FRICTION]"

*What causes users to repeatedly listen to the same content?*
- `repeat_listen_reason` — the reason the user gives for repeating/not exploring music, in their own words, or null
- `workaround_mentioned` — whether the user describes a workaround they built
- `workaround_description` — exactly what the user does instead

*Which user behaviors emerge consistently across reviews?*
- `behaviour_pattern` — open-text description of the user's behaviour in the model's own words, or null
- `pattern_evidence` — one sentence from the source text justifying the extracted pattern

*What unmet needs emerge consistently across reviews?*
- `unmet_need` — framed as "User needs [X] but the product currently [Y]"

**Stores all classified feedback in a local SQLite database** for structured querying and in **ChromaDB** (local vector database with sentence-transformer embeddings) for natural language retrieval — no cloud database, no cost.

**Delivers two outputs through a two-page web application:**

A **PM dashboard** showing open-field tallies, top core complaints, a workaround tracker, and a verbatim quotes feed. Note: In v1, the dashboard shows raw extractions (open text). Grouping these into definitive "segments" or "categories" is a Phase B clustering step that happens only after real themes emerge from the data.

A **RAG-powered research chat interface** where any PM can ask questions in plain English and receive synthesized answers grounded in real, **verbatim-verified** user quotes across all four sources — every quote in every answer is validated as a substring of a real source document to prevent AI hallucination. Filterable by date range, platform, topic, core complaint, and signal type.

---

### Who This Serves

**A PM on a discovery or personalization team** — asks "what specific barriers do users describe when using Discover Weekly?" and gets a sourced answer with **verbatim-verified quotes** in seconds, instead of spending hours reading App Store reviews.

**A growth PM investigating retention** — filters for churned users across all platforms and sees the common core complaints that preceded churn, alongside the users' behaviour patterns.

**Any PM building recommendation-driven consumer products** — points the system at a different product's review sources and gets the same depth of behavioral classification without rebuilding anything.

---

### What Makes This Different

This is not a sentiment dashboard. It is not a review aggregator. It is a behavioral research system.

The classification layer extracts 12 dimensions of user psychology and context — topics, core complaints, trust levels, repeating reasons, workaround behavior, unmet needs — without forcing them into predefined dropdowns. This grounded-theory approach allows actual themes to emerge from the data, revealing patterns invisible to any single metric or confirmation-biased analysis.

The RAG layer makes the entire corpus queryable in natural language so insights compound over time rather than expiring after a sprint. **Every quote in every answer is verified** — the system checks that every quoted string actually exists in a source document before displaying it, preventing AI hallucination from eroding PM trust. The nightly refresh ensures every answer reflects what users are saying this week, not last quarter. And unlike existing tools, everything runs locally — SQLite for structured data, ChromaDB for vectors — so there are no cloud costs and no data leaving your machine.

The system is product-agnostic by design. The six data sources and 12 classification dimensions are configured for Spotify's discovery problem today. Any PM can reconfigure them for a different product's feedback sources and a different set of behavioral questions tomorrow.

---

### Success Looks Like

A PM asks "Why do users with high listening hours still feel like they're not discovering anything new?" and receives a synthesized answer citing 5+ sourced quotes from across App Store, Play Store, and Spotify Community — in seconds.

The dashboard surfaces raw, unstructured behavioral patterns per week that would not be visible from internal usage metrics alone — allowing the team to group them into actual insights later.

The workaround detection consistently identifies user-built coping mechanisms that reveal where native product features are failing — giving the product team a direct signal for what to fix.

The system processes new feedback on schedule while the server is running, and a PM opening it Monday morning sees insights from conversations that happened over the weekend.
# GrantScope Newbie Mode + AI Integration: Comprehensive Implementation Plan

Last updated: 2025-09-08
Owner: Team GrantScope

## TL;DR
We will add a Newbie Mode and integrate AI across key pages to guide first-time grant seekers. This plan details architecture, feature flags, file-by-file changes, acceptance criteria, testing, and rollout steps. All changes use existing patterns (Streamlit multipage, config getters, LlamaIndex/OpenAI) and are guarded by feature flags.

## Goals
- Make GrantScope friendly for users with little grant experience
- Provide plain-English guidance and actionable next steps
- Integrate AI safely: grounded, explainable, and cancellable
- Preserve advanced tools for experienced users

## Non-Goals
- No backend services or databases (Streamlit-only)
- No new third-party libraries without approval
- No changes to data sources or schema beyond minor preprocessing safety

## Architecture Overview
- Streamlit multipage app (pages/) with shared state in utils/app_state.py
- Charts in plots/; data loaders in loaders/; AI wiring in loaders/llama_index_setup.py
- AI chat UI consolidated in utils/chat_panel.py with streaming via GS_ENABLE_CHAT_STREAMING
- Newbie Mode and features gated by config feature flags, read via config getters (never os.getenv in app code)

## Feature Flags (config)
- GS_ENABLE_NEWBIE_MODE: Enables Newbie Mode UI/flows
- GS_ENABLE_CHAT_STREAMING (existing): Enables streaming chat + cancel
- GS_ENABLE_LEGACY_ROUTER (existing): Temporary legacy fallback

Update config.py to expose:
- is_feature_enabled("NEWBIE_MODE") and feature_flags["NEWBIE_MODE"]

## High-Level Roadmap
1) Phase 1: Onboarding, roles, plain-English chart helpers (Quick Wins)
2) Phase 2: New pages (Project Planner, Timeline Advisor, Success Stories, Budget Check)
3) Phase 3: AI integration (newbie-friendly prompts, grounded context, recommendations)
4) Phase 4: Polish, accessibility, docs, tests

---

## Detailed Implementation

### 0) Prereqs and Conventions
- Use config getters (get_openai_api_key, is_feature_enabled, feature_flags)
- Avoid os.getenv in app code
- Raise exceptions or show st.error; do not print/exit
- Absolute imports from repo root per pytest.ini (pythonpath=.)
- Keep functions pure where feasible; annotate types; avoid Any

### 1) Onboarding Wizard (Newbie Mode)
Files:
- app.py (gate initial experience)
- utils/app_state.py (session state keys)
- utils/onboarding.py (new helper with onboarding components)

Behavior:
- If GS_ENABLE_NEWBIE_MODE and user has no session flag onboarding_complete, show onboarding wizard before pages
- Collect: project_type, budget_range, timeline, experience
- Persist to st.session_state.user_profile

Acceptance:
- First launch shows onboarding; subsequent navigations skip
- Sidebar shows selected experience and allows reset

### 2) Role Model Revamp (Experience-Based)
Files:
- utils/app_state.py (sidebar_controls)

Behavior:
- Replace roles with:
  - "I'm new to grants" (simplified pages + helpers)
  - "I have some experience" (current Normal)
  - "I'm a grant professional" (current Analyst)
- Filter pages shown in navigation by role

Acceptance:
- Role persists across pages
- Role affects which pages and which UI helpers render

### 3) Plain-English Helpers for Charts
Files:
- plots/data_summary.py
- plots/grant_amount_distribution.py
- plots/grant_amount_scatter_plot.py
- plots/grant_amount_heatmap.py
- plots/grant_description_word_clouds.py
- plots/treemaps_extended_analysis.py
- plots/general_analysis_relationships.py

Behavior:
- Add optional explainers below each chart when role == Newbie or feature flag is on
- Use st.info/st.success to show: What this chart means, Why it matters, What to do next
- Maintain existing visuals; do not change data logic

Acceptance:
- Explainers appear only in Newbie Mode or when toggled on
- No layout regressions on narrow screens

### 4) Glossary + Contextual Help
Files:
- utils/help.py (new)
- utils/app_state.py (sidebar button to open glossary expander)

Behavior:
- Provide plain-English definitions for: funder, recipient, grant_amount, funder_type, grant_subject, amount_usd, year_issued
- Sidebar button opens an expander showing the glossary

Acceptance:
- Glossary accessible from any page; copy is 8th-grade reading level

### 5) Smart Recommendations (Data-First, AI-Optional)
Files:
- utils/recommendations.py (new)
- plots/ data-summary and distribution pages (hook-in optional panel)

Behavior:
- Generate recommendations from DataFrame (local): e.g., budget realism, local funders, recent activity
- If OpenAI key available (via config), augment with AI suggestions grounded by context sample
- Guardrails: Only use Known Columns; include current filters + compact sample

Acceptance:
- Works offline (no key) with local heuristics
- With key, AI adds 1–3 actionable next steps in plain English

### 6) New Pages
A) pages/9_Project_Planner.py
- Step-by-step form to define Problem, Beneficiaries, Activities, Success metrics
- Save summary to session; allow download

B) pages/10_Timeline_Advisor.py
- Choose urgency and time available; show plan and sample timeline table

C) pages/11_Success_Stories.py
- Hard-coded stories to inspire; later make data-driven

D) pages/12_Budget_Reality_Check.py
- Visualize amount buckets; compare with user budget; show guidance

Acceptance:
- Each page loads independently; navigable from sidebar
- No API key required

### 7) AI Chat Enhancements (Newbie-Friendly)
Files:
- utils/chat_panel.py
- loaders/llama_index_setup.py (ensure model config via config)
- utils/utils.py (already builds page prompt; extend with “newbie instruction”)

Behavior:
- Add wrapper to rewrite newbie questions into clear prompts (e.g., “Explain like I’m new… Give 3 next steps”)
- Keep streaming + cancel (GS_ENABLE_CHAT_STREAMING)
- Include grounded context: Known Columns, Current Filters, Compact Sample
- Per-page chat history stays in session

Acceptance:
- If streaming flag off, non-streaming response works
- Cancel button leaves UI consistent
- Prompts never access columns not in Known Columns

### 8) Advisor Interview Page (Newbie Overlay)
Files:
- pages/0_Grant_Advisor_Interview.py
- advisor/* (no API changes; UI-only improvements)

Behavior:
- If role == Newbie, show a simplified pre-checklist and “What you’ll get” panel
- Add a mini-action plan output in plain English (tie to MUNICIPAL_IMPROVEMENTS.md voice)
- Keep advanced controls for other roles

Acceptance:
- Newbie gets simpler UI and clear outputs
- Existing advanced users unaffected

### 9) UI Copy and Accessibility
- 8th-grade reading level (per MUNICIPAL_IMPROVEMENTS.md)
- Short paragraphs, bullet points, bold keywords
- Mobile readability: avoid wide tables without use_container_width

### 10) Performance and Caching
- Cache expensive groupbys (st.cache_data)
- Avoid recomputing splits/explodes in multiple pages
- Reuse compact sample for AI prompts

---

## File-by-File Change List

app.py
- Gate onboarding in main() when is_feature_enabled("NEWBIE_MODE") and onboarding not complete
- Render sidebar_controls() after onboarding

utils/app_state.py
- Add user_profile keys; persist role
- Sidebar: experience selector and glossary button
- Hide Streamlit default nav (existing)

utils/onboarding.py (new)
- Functions: render_onboarding_wizard(), save_user_profile()

utils/help.py (new)
- GLOSSARY dict and render_glossary()

utils/recommendations.py (new)
- class GrantRecommender with data-first and AI-augmented methods

utils/chat_panel.py
- newbie_friendly_chat(prompt, context); integrate with existing chat panel
- Respect GS_ENABLE_CHAT_STREAMING; support cancel

plots/*
- Add optional explainers per chart; use role/flag to display
- Persist minimal chart state in st.session_state for AI context (e.g., ds_top_n)

pages/
- 9_Project_Planner.py, 10_Timeline_Advisor.py, 11_Success_Stories.py, 12_Budget_Reality_Check.py
- Update existing page titles to plain-English subtitles (not breaking filenames)

loaders/llama_index_setup.py
- Ensure model is taken from config.get_openai_model() or default

config.py
- Add feature flag NEWBIE_MODE in feature_flags

---

## Security and Privacy
- No secrets in code or logs; use config getters and st.secrets precedence
- Do not persist API keys in session or disk
- AI prompts include only grounded, minimal context samples (no PII fields)

## Testing Plan
Commands (from CRUSH.md):
- pytest
- pytest -q -k "advisor and not slow"

Add tests:
- tests/test_onboarding.py: wizard sets session and gates main
- tests/test_roles.py: role controls page visibility
- tests/test_recommendations.py: local heuristics work without key; AI path stubbed
- tests/test_chat_guardrails.py: prompt uses Known Columns only; streaming fallback
- tests/test_pages_smoke.py: new pages import and render with sample data

When env changes in tests, call refresh_cache() if provided by config utilities.

## Lint/Type
Optional (from CRUSH.md):
- ruff check .
- black --check .
- mypy .

## Acceptance Criteria (Checklist)
- Onboarding: First-time users see wizard; profile saved; can reset
- Roles: Experience selection affects nav + helpers
- Charts: Plain-English explainers visible in Newbie Mode
- Recommendations: Local + AI-augmented (if key); safe when no key
- New pages: Planner, Timeline, Stories, Budget all functional
- Chat: Newbie prompts, streaming/cancel, grounded context
- Advisor Interview: Simplified overlay for Newbie role
- Docs: This plan + INTEGRATION_GUIDE.md available to team

## Rollout Plan
- Phase 1 behind GS_ENABLE_NEWBIE_MODE=1; default off
- Internal QA with sample dataset (data/sample.json)
- Enable for limited users; monitor feedback
- Make Newbie Mode default after stability

## Runbook
- Local: streamlit run app.py
- Flags (env or secrets):
  - GS_ENABLE_NEWBIE_MODE=1
  - GS_ENABLE_CHAT_STREAMING=1
- No secrets? Chat panels show UI to input API key for session only

## Risks and Mitigations
- Prompt drift: enforce Known Columns in prompt assembly
- Performance: cache groupbys; bound sample size in prompts
- UI overload: hide helpers for advanced roles; use expanders

## Future Work
- Save user projects to file for later sessions
- Data-driven success stories
- Multi-language UI

---

## Developer Notes
- Follow existing import and typing style
- Keep modules small and pure
- Use st.error/warning/info for UI messaging; never print
- Prefer absolute imports from repo root

Happy shipping! If you need to extend this, start with Phase 1 and ship in small PRs guarded by feature flags.

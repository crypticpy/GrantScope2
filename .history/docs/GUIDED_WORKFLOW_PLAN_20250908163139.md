## Guided, Context-Aware GrantScope Workflow (Beginner-Friendly)

Audience: New or non-technical users (after‑school programs, health initiatives, social services). Tone: 8th‑grade, friendly, step-by-step. Goal: Help users use their data to find funders, plan a project, and produce a clear, downloadable workbook with suggestions they can use in grant applications.

---

### 1) Lightweight Intro + Profile (2 minutes)

- Why: Personalize the experience and tone; keep it simple.
- Collect: experience level, org type, region, main goal (1–2 lines).
- Implementation:
  - Use existing `utils/onboarding.py` wizard; make it default on first run (flag: `GS_ENABLE_NEWBIE_MODE`).
  - Persist to session as `user_profile` via `utils.app_state.set_session_profile()`.
  - Add “Skip for now” path; defaults to beginner tone.

Result: A short profile we can reuse across pages.

---

### 2) Data Setup

- Upload Candid JSON or use sample; show simple checklist.
- Implementation:
  - Uses existing `utils.app_state.get_data()` and sidebar uploader.
  - Keep error messages simple and actionable.

Result: Dataframe loaded; ready for charts and chat.

---

### 3) Page Flow and Personalization

We guide users through a clear path. Each page’s chat uses both the data context and the user profile to keep answers simple and relevant.

Proposed order:

1. Data Summary → 2. Grant Amount Distribution → 3. Scatter (over time) → 4. Heatmap → 5. Treemaps → 6. Word Clouds → 7. Relationships → 8. Top Categories → 9. Budget Reality Check → 10. Project Planner → 11. Advisor Report

Implementation:

- Chat preface now includes audience tone from `_audience_preface()` and chart context from `resolve_chart_context(chart_id)`.
- Update `utils/chat_panel._get_starter_prompts(chart_id)` with beginner questions tailored per chart (already implemented). Keep language plain and coach-like.
- Add profile-based seasoning (org type/region/goal) to prompts and final answers (see Section 6).

---

### 4) Beginner Starters in Chat (Already Done)

- Dropdown label: “Unsure what to ask — select a starter”.
- Three per chart page focused on:
  - What am I seeing?
  - What should I look for?
  - What can I do next?
- Autosend when selected.

---

### 5) Clear Teaching Moments on Each Chart Page

Add a small “What this chart tells you” expander per chart page with plain tips. This boosts confidence and reduces confusion.

Implementation tasks:

- Add a helper in `utils/help.py` (or reuse `render_page_help_panel`) to render a short 3–5 bullet guide per page. Keep it lightweight and collapsible.

---

### 6) Personal Context Injection (Profile → Chat)

Make the AI answers feel “for me.”

- Source: `user_profile` (experience, org type, region, goal) from `utils.app_state`.
- Injection points:
  1. Chat tone preface (already present) — extend to sprinkle profile: org type and region.
  2. `tool_query()` and `query_data()` — prepend a small “User Context” header to the prompt.

Concrete change:

- In `utils/chat_panel._audience_preface()`, append short context when available, e.g. “User works with a school in California; goal: expand after‑school programs.”
- In `loaders/llama_index_setup.tool_query()` and `.query_data()`, include a compact “User Context” string alongside Known Columns and Chart Context.

---

### 7) Budget Reality Check → Project Planner → Advisor Report

Guide users from data to a practical plan.

Flow:

1. Budget Reality Check (existing page) — pick a realistic budget using distributions and examples.
2. Project Planner — outline problem, solution, who benefits, simple timeline.
3. Advisor Pipeline — runs analysis and produces a report with funders, focus areas, and next steps.

Implementation:

- Add a “Continue →” button at bottom of each page to move to the next recommended page.
- Persist chosen budget and key planner fields in `st.session_state` (e.g., `planner_budget_usd`, `planner_problem`, `planner_outcomes`).
- Have the chat reference these values in answers when present.

---

### 8) Workbook Export (Download)

Give users a single export with:

- Profile summary, chosen budget, project plan fields
- A few key charts (as images or short tables)
- AI notes and recommendations
- Draft proposal language snippets

Implementation tasks:

- Create an export builder in `advisor/renderer.py` to assemble a Markdown and HTML bundle.
- Reuse existing `download_text()` and `download_multi_sheet_excel()`; add `download_markdown("workbook.md")` helper.
- Add a “Save My Workbook” button on the Advisor Report page; save as `.md` and optionally `.pdf` (if available in environment).

---

### 9) Guardrails and Simplicity

- Keep language plain; avoid data jargon.
- Chat answers must cite what they use: “Based on the current view and your goal…”
- Never invent fields; rely on Known Columns (already enforced in prompts and tools).

---

### 10) Engineering Tasks (Detailed)

1. Profile context in chat

   - [ ] Extend `_audience_preface()` to include org type, region, and goal (if present).
   - [ ] Update `tool_query()`/`query_data()` to include “User Context:” string in prompt assembly.

2. Page help coaching

   - [ ] Add/extend `utils/help.render_page_help_panel()` with quick tips per chart page.
   - [ ] Call it in each chart page with `audience="new"` when Newbie Mode is on.

3. Page navigation flow

   - [ ] Add “Continue →” buttons between recommended pages (config-driven so pros can disable).
   - [ ] Store simple breadcrumbs so users can jump back easily.

4. Planner + Budget persistence

   - [ ] Define shared keys in `utils/app_state` (e.g., `planner_*`, `budget_selected_range`).
   - [ ] Use them in chat context and final report.

5. Workbook export

   - [ ] Add `build_workbook_bundle(profile, planner, budget, insights)` in `advisor/renderer.py`.
   - [ ] Provide `download_text` convenience for Markdown; optional HTML/PDF.

6. QA & Tests
   - [ ] Unit tests for `_audience_preface()` context infusion.
   - [ ] Tests for `_get_starter_prompts(chart_id)` per chart family.
   - [ ] Smoke test for export builder output.

---

### 11) Minimal Data Flow Diagram

Profile (onboarding) → Sidebar (data + API key) → Chart Pages (help + chat with starters) → Budget Check → Project Planner → Advisor Pipeline → Workbook Export

Each arrow passes a small set of values via `st.session_state` so chat and pages stay aware of the user’s goal and choices.

---

### 12) Rollout Plan

1. Phase 1 (1–2 days): Starter prompts per chart (done), help panels, profile context in chat.
2. Phase 2 (2–3 days): Page flow buttons, planner/budget persistence, basic export.
3. Phase 3 (3–4 days): Polishing, richer export, tests, docs.

Done right, users get a friendly path from “I’m new” to a saved workbook with funders, a realistic budget, a simple plan, and draft language they can adapt for grants.

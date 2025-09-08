# Changelog

## Unreleased

- Align figures with datapoint filtering so charts and tables agree
  - Figures now use the same normalized, needs-filtered DataFrame as metrics
- Robust Targeted Focus fallback when SQL yields no rows
  - Programmatic computation of subject x population totals and counts
- Municipal audience targeting and clearer section requirements in Stage 4
  - Plain-language sections aimed at public sector readers
- Live Streamlit progress tracker
  - Pipeline runs in a background thread and the UI auto-reruns periodically
- Minor stability improvements
  - Thread-safe progress updates; conservative UI-state writes

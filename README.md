# browser-agent-a11y-tree-grounding

> **Era:** 2023–2024 · Senior AI Engineer focus area (web agents). Technique from 2023, reimplemented in 2026.

A dependency-free browser-agent core built around compressed accessibility observations and
set-of-marks grounding. It parses real HTML, computes roles and accessible names, assigns stable
element IDs and per-observation marks, emits actual SVG set-of-marks images, and executes scripted
actions against deterministic local websites. CPU tests require no browser package, external site,
model SDK, or API key.

## Problem

Raw HTML contains substantial markup irrelevant to the next action, while a model response such as
“click the second button” is ambiguous after the page changes. The agent needs a compact semantic
observation and an explicit, checkable link from each visual mark to the exact DOM element. It must
also reject marks from an old page rather than accidentally applying them to a new one.

## Method

1. **DOM and accessibility tree.** `HTMLParser` builds a parent-linked DOM. The accessibility pass
   handles explicit roles, common native roles, `aria-label`, `aria-labelledby`, associated labels,
   alternative text, values, checked/disabled state, and hidden subtrees. Generic containers are
   flattened; scripts, styles, hidden controls, and empty text nodes are omitted.
2. **Stable IDs and marks.** An element ID is a SHA-256 digest of its semantic signature (explicit
   `data-element-id`/HTML ID when available, tag, role, name, and duplicate ordinal). IDs survive
   reparsing and unrelated content changes. Interactive elements receive short numeric marks in
   document order for each observation.
3. **Compression and screenshots.** The serialized tree retains roles, names, values, state, IDs,
   and marks under node/character limits. The SVG renderer draws a labeled wireframe row for each
   accessibility node and a numbered badge for every actionable element. These are real, valid SVG
   images with `data-mark` and `data-element-id` metadata, not ASCII placeholders.
4. **Grounding.** `click`, `type`, and `select` actions carry a mark plus observation revision.
   Grounding resolves mark → stable element ID → current node and validates action/role compatibility.
   Stale revisions, unknown marks, disabled elements, and incompatible actions are rejected.
5. **Deterministic execution.** `LocalBrowser` supports links, history, text fields, checkboxes,
   radio buttons, selects, and GET forms. `ScriptedPolicy` expresses semantic intents but must find
   the current mark for every target. `BrowserAgent` executes only grounded actions and checks an
   independent task goal after `finish`.

## Results

Measured on 2026-11-14 over four deterministic in-memory tasks. Success means the final URL/form
state satisfies the independent goal. Tokens are regex word/punctuation **estimates**, not a
provider tokenizer. SVGs are wireframe set-of-marks renderings, not pixel browser captures.

| Task | Success | Steps | Compressed tokens | Raw HTML tokens | Tokens/step | Reduction |
|---|:---:|---:|---:|---:|---:|---:|
| grounding-search | yes | 4 | 310 | 345 | 77.5 | 10.1% |
| accessibility-search | yes | 4 | 310 | 345 | 77.5 | 10.1% |
| about-navigation | yes | 2 | 125 | 147 | 62.5 | 15.0% |
| preferences-form | yes | 4 | 226 | 377 | 56.5 | 40.1% |

Overall local success was **4/4**. Across all 14 steps, compressed observations averaged
**69.36 estimated tokens/step** and used **20.02% fewer** estimated tokens than the corresponding
raw HTML. These are local functional measurements only: no WebArena, Mind2Web, real-model, or
external-website benchmark was run. Full records are in `results/local_benchmark.json`; eight
actual initial/final marked SVGs are under `results/screenshots/`.

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
python scripts/benchmark.py
```

The tests cover accessible-name computation, hidden filtering, stable IDs, bounded compression,
valid SVG metadata, stale/unknown/wrong-role grounding, JSON action validation, typed GET forms,
checkbox/select state, navigation, and complete scripted local tasks. The benchmark rewrites the
result files and screenshots with fresh measured values.

## Limitations

- The SVG is a deterministic semantic wireframe, not a layout- or pixel-accurate screenshot. There
  is currently no JavaScript engine, CSS layout, network browser, or Playwright adapter.
- IDs based on HTML IDs are stable across label edits; IDs without an explicit anchor use the
  accessible name and can change when that name changes. Duplicate identical elements use order.
- The local browser implements deterministic links and GET forms only. Non-submit buttons,
  JavaScript applications, uploads, frames, and dynamic accessibility events are out of scope.
- Token reduction depends on page shape and is measured with an approximate tokenizer. Scripted
  task success demonstrates grounding and execution correctness, not real-LLM web competence.

## References

- Zhou et al. *WebArena: A Realistic Web Environment for Building Autonomous Agents.* 2023. arXiv:2307.13854
- Deng et al. *Mind2Web: Towards a Generalist Agent for the Web.* 2023. arXiv:2306.06070
- Yang et al. *Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V.* 2023. arXiv:2310.11441
- He et al. *WebVoyager: Building an End-to-End Web Agent with Large Multimodal Models.* 2024. arXiv:2401.13919

## License

MIT

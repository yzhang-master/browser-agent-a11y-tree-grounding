# browser-agent-a11y-tree-grounding

> **Era:** 2023–2024 · Senior AI Engineer focus area (web agents). Technique from 2023, reimplemented in 2026.

A dependency-free local web-agent environment with HTML/accessibility-tree parsing, stable
marks, actual SVG set-of-marks renderings, and deterministic action grounding. Implementation
and local measurements are documented below as they are completed.

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

## License

MIT

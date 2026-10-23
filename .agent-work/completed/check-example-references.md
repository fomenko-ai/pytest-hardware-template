---
id: check-example-references
status: complete
owner: codex
updated: 2026-10-23
---

# Check relocated example references

## Result

Checked documentation, skills, code, and configuration for references to the former root example
package. Corrected the guide's line 39 display label to docs/examples/custom_entities.py; its
relative target was already correct. Test imports, skill links, README targets, and ty use the
new location. ADR-local examples and the historical move description are accurate.

## Verification

- Repository-wide search: no stale active root-example imports or link targets found. Guide
  display label corrected; ADR-local examples and historical move description remain accurate.
- Checked 89 tracked local Markdown targets: all resolve.
- Full ./scripts/ci.sh: passed; no hardware tests were run.

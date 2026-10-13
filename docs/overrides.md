# Overrides — reviewed corrections to the database

Overrides are the only way to change content without changing the parser. They live in `data/overrides/*.yaml`, are
applied at the end of `python -m lh build` (`lh/model/overrides.py`), and are recorded in the `override_log` table.
Objects changed by an override get `status = 'overridden'`; the round-trip check skips them and reports their count,
because they now differ from the PDF on purpose.

Each entry is a YAML mapping; every entry needs `id`, `action`, `reason`, `evidence`.

```yaml
# data/overrides/psalter.yaml
- id: T-FJ-10                         # the TODO.md item this resolves
  action: replace                     # replace text inside one object's payload
  object: ps.094.12-24.xxxx           # object id (python -m lh find / lh show)
  find: "<v>24</v>"
  replace: ""
  reason: "LH prints a spurious verse label 24 (Ps 94 has 23 verses); owner approved 2026-10-20."
  evidence: "LH-Per_annum.pdf p.729; Nova Vulgata Ps 94"

- id: T-DUP-17
  action: merge                       # re-point every occurrence of `object` to `into`, delete `object`
  object: ant.in-sanctitate-serviamus-domino.3b391d
  into: ant.in-sanctitate-serviamus-domino.f8899a
  reason: "Same antiphon; one printing lacks a comma. Majority reading kept."
  evidence: "16 vs 18 printings; e.g. PA p.350"

- id: T-FJ-1
  action: note                        # decision only, no data change
  reason: "Felix Just typo (119:333-40 for 119:33-40); LH is correct."
  evidence: "catholic-resources.org/LoH/Psalter.html; LH-Per_annum.pdf p.256"
```

Rules
- `replace` fails the build if `find` does not occur in the object — overrides never apply silently to nothing.
- Prefer fixing the parser when the PDF is right and the extraction is wrong; overrides are for errors **in the
  source** (or deliberate editorial decisions) and must cite the evidence.
- When an override resolves a `TODO.md` item, mark the item `[x]` with the override id.

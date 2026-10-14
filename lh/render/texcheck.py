"""Static checks of generated book LaTeX: labels defined (\\objlabel, \\dayhead, \\readhead), references used
(\\seepage, \\pg, \\pgref), duplicate labels and unresolved references. Used by the tests and `lh book`."""
from __future__ import annotations

import collections
import re

LABEL_RE = re.compile(r"\\objlabel\{([^}]*)\}|\\dayhead\{(?:[^{}]|\{[^{}]*\})*\}\{(?:[^{}]|\{[^{}]*\})*\}"
                      r"\{(?:[^{}]|\{[^{}]*\})*\}\{([^}]*)\}|\\readhead\{(?:[^{}]|\{[^{}]*\})*\}\{([^}]*)\}")
REF_RE = re.compile(r"\\(?:seepage|pgref|pg|pageref)\{([^}]*)\}")


def labels(tex: str) -> collections.Counter:
    c = collections.Counter()
    for m in LABEL_RE.finditer(tex):
        c[next(g for g in m.groups() if g is not None)] += 1
    return c


def refs(tex: str) -> set[str]:
    return set(REF_RE.findall(tex))


def check(tex: str) -> dict:
    lab = labels(tex)
    rf = refs(tex)
    return {"labels": len(lab), "duplicates": sorted(k for k, n in lab.items() if n > 1),
            "unresolved": sorted(rf - set(lab)), "refs": len(rf)}

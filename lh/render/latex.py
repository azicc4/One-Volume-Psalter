"""Object payload (inline markup <r> <i> <v>) → LaTeX. One function per object type."""
from __future__ import annotations

import re

from lh.model.canon import paragraphs

_SPECIAL = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#",
            "^": r"\^{}", "_": r"\_", "%": r"\%", "~": r"\textasciitilde{}"}
_TAG = re.compile(r"(</?[irv]>)")


def esc(s: str) -> str:
    return "".join(_SPECIAL.get(c, c) for c in s)


def tex(markup: str, marks: bool = True) -> str:
    """Inline markup → LaTeX. * and † become red pointing marks when marks=True."""
    out, stack = [], []
    # spaces at the edge of a styled run go outside it ("Allelúia,<r> prouti" → "Allelúia, <r>prouti"): a space
    # right after "{\color{rubric}" following punctuation is lost in the PDF (babel-latin)
    markup = re.sub(r"(<[irv]>)(\s+)", r"\2\1", markup or "")
    markup = re.sub(r"(\s+)(</[irv]>)", r"\2\1", markup)
    for tok in _TAG.split(markup):
        if not tok:
            continue
        if tok in ("<i>", "<r>", "<v>"):
            stack.append(tok)
            out.append({"<i>": r"\textit{", "<r>": r"{\color{rubric}", "<v>": r"\vinline{"}[tok])
        elif tok in ("</i>", "</r>", "</v>"):
            if stack:
                stack.pop()
                out.append("}")
        else:
            t = esc(tok)
            if marks:
                t = t.replace("*", r"\mediant{}").replace("†", r"\flex{}")
            out.append(t)
    out.extend("}" for _ in stack)
    s = "".join(out)
    s = s.replace("{\\color{rubric}\\flex{}}", "\\flex{}").replace("{\\color{rubric}\\mediant{}}", "\\mediant{}")
    return s


def label(s: str) -> str:
    """Object id → safe LaTeX label."""
    return "o:" + re.sub(r"[^A-Za-z0-9.:-]", "-", s)


def ant(p: dict) -> str:
    return tex(p["text"])


def pairs(p: dict) -> str:
    out = []
    for k, v in p["pairs"]:
        out.append((r"\Vs " if k == "V" else r"\Rs ") + tex(v))
    return r"\par ".join(out)


def prose(p: dict) -> str:
    return r"\par ".join(tex(x) for x in paragraphs(p.get("lines", [])))


def hymn(p: dict) -> str:
    st = [r"\\ ".join(tex(l, marks=False) for l in stanza) for stanza in p["stanzas"]]
    return r"\begin{hymn}" + r"\stanza ".join(st) + r"\end{hymn}"


def preces(p: dict) -> str:
    out = []
    if p.get("intro"):
        out.append(tex(p["intro"]))
    if p.get("response"):
        out.append(r"\textit{" + tex(p["response"]) + "}")
    if p.get("response_alt"):                      # "Vel: …" alternative response (Sanctis, SP 287)
        out.append(tex(p["response_alt"]))
    for pet in p.get("petitions", []):
        alt = r"\condlabel{(vel:)}" if pet.get("alt") else ""
        out.append(r"\noindent\hangindent=1em " + alt + tex(pet["a"]) + r"\\ \hspace*{0.6em}{\color{rubric}—} " + tex(pet["b"]))
    if p.get("tail"):
        out.append(tex(p["tail"]))
    return r"\par\vspace{1pt}".join(out)


def reading(p: dict) -> str:
    out = []
    for x in p.get("intro", []):
        out.append(r"{\small " + tex(x) + "}")
    for x in p.get("meta", []):
        out.append(r"{\centering\footnotesize " + tex(x) + r"\par}")
    out += [tex(x) for x in paragraphs(p.get("lines", []))]
    return r"\par ".join(out)


def te_deum(p: dict) -> str:
    out = []
    for kind, x in p["lines"]:
        out.append(r"\rubr{" + tex(x, marks=False) + "}" if kind == "rubric" else r"\noindent\hangindent=1.5em " + tex(x))
    return r"\par ".join(out)


def canticle_lines(lines: list[dict]) -> str:
    """Psalm/canticle lines (from an object payload) → verse paragraphs."""
    out = []
    for l in lines:
        t = tex(l["t"])
        if l.get("refrain"):
            out.append(r"\par{\footnotesize\rubric{" + tex(l["t"], marks=False) + r"}}\par")
        elif l.get("v"):
            out.append(r"\psl{" + esc(l["v"]) + "}{" + t + "}")
        elif l["x"] >= 2:
            out.append(r"\psk{" + t + "}")
        else:
            out.append(r"\psc{" + t + "}")
    return "\n".join(out)


def citation(otype: str, p: dict) -> str:
    """Scripture citation shown next to a reading's title: English style when the book is known
    (e.g. "(1 Th 5, 9-10)" → "1 Thess 5:9-10"), otherwise as printed in the source."""
    if otype in ("lectio_brevis", "responsory", "resp_breve", "versicle"):
        from lh.psalter.refs import english_ref
        ref = (p.get("ref") or "").strip()
        return esc(english_ref(ref)) if ref else ""
    if otype == "reading":
        from lh.model.canon import plain
        return esc(plain(" ".join(p.get("intro", []))))
    return ""


RENDER = {
    "ant": ant, "versicle": pairs, "responsory": pairs, "resp_breve": pairs, "lectio_brevis": prose,
    "oratio": prose, "prayer": prose, "text": prose, "hymn": hymn, "preces": preces, "reading": reading,
    "te_deum": te_deum, "rubric": lambda p: r"\rubr{" + tex(p["text"], marks=False) + "}",
}


def render(otype: str, payload: dict) -> str:
    return RENDER[otype](payload)

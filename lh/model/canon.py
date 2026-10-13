"""L4: canonical objects.

`canon(element)` splits a parsed element into
  * an OBJECT (the text that is the same wherever it is printed: identified by a hash of its normalized text), and
  * occurrence-level EXTRA (things that legitimately vary per printing: antiphon number, leading-† intonation marks
    in psalms, whether Gloria Patri was printed, page-induced stanza breaks, the psalm heading as printed here).

`restore(type, payload, extra)` rebuilds the printed text from object + extra. The round-trip check compares that
against the source lines, proving the database is lossless with respect to the PDFs.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from lh.extract.lines import norm_space

TAG_RE = re.compile(r"</?(?:i|r|v)>")
VERSE_TAG_RE = re.compile(r"<v>[^<]*</v>\s*")
DAGGER = "<r>†</r> "

PREFIX = {
    "hymn": "hym", "ant": "ant", "psalm": "ps", "canticle": "cant", "versicle": "vr", "reading": "lec",
    "responsory": "resp", "lectio_brevis": "lb", "resp_breve": "rb", "preces": "prec", "oratio": "or",
    "te_deum": "tedeum", "prayer": "pr", "text": "txt", "rubric": "rub", "link": "ref", "ordinary_ref": "ref",
}
STRUCTURAL = {"label", "marker"}


def plain(s: str, verses: bool = False) -> str:
    """Markup → plain text (verse numbers dropped unless verses=True)."""
    if not verses:
        s = VERSE_TAG_RE.sub("", s)
    return norm_space(TAG_RE.sub("", s))


def fold(s: str) -> str:
    """Accent/ligature folding for slugs and search: 'Dómine, æternæ' → 'domine, aeternae'."""
    s = s.replace("æ", "ae").replace("Æ", "Ae").replace("œ", "oe").replace("Œ", "Oe").replace("ǽ", "ae")
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def slug(text: str, n: int = 4) -> str:
    words = re.findall(r"[a-z0-9]+", fold(plain(text)))
    return "-".join(words[:n]) or "x"


def h(s: str, n: int = 6) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def paragraphs(lines: list[list]) -> list[str]:
    """[[xclass, markup], …] → paragraphs. A paragraph starts at an indented line (xclass 1)."""
    paras: list[str] = []
    for cls, t in lines:
        if not paras or cls == 1:
            paras.append(t)
        else:
            paras[-1] = paras[-1] + " " + t
    return [norm_space(p) for p in paras]


def strip_dagger(t: str) -> tuple[str, bool]:
    if t.startswith(DAGGER):
        return t[len(DAGGER):], True
    return t, False


INLINE_V_RE = re.compile(r"<v>([^<]+)</v>")


def unit_verses(lines: list[dict]) -> tuple[list[str], bool]:
    """Ordered verse labels of a psalm/canticle unit, including verse numbers printed mid-line.
    Also returns starts_mid: True when the unit opens with the second half of a verse (no number on line 1)."""
    out: list[str] = []
    for l in lines:
        for v in ([l["v"]] if l.get("v") else []) + INLINE_V_RE.findall(l["t"]):
            v = v.strip()
            if v and v not in out:
                out.append(v)
    first = lines[0] if lines else None
    starts_mid = bool(first) and not first.get("v") and not first["t"].lstrip().startswith("<v>") and not first.get("resp")
    return out, starts_mid


def psalm_base(hebr: str) -> int:
    return int(re.match(r"\d+", hebr).group(0))


def canticle_slug(ref: str) -> str:
    r = fold(ref).replace("cf. ", "")
    r = re.sub(r"[^a-z0-9,\-;. ]", "", r)
    r = re.sub(r"\s*,\s*", "_", r.strip())
    r = re.sub(r"[ .;]+", "", r)
    return r[:40]


def canon(e) -> tuple[str, dict, str, dict] | None:
    """Return (object_type, payload, identity_key, occurrence_extra) or None for structural elements."""
    c = _canon(e)
    if c is not None and e.data.get("choice"):
        c[3]["choice"] = e.data["choice"]     # printed number of a numbered alternative ("1 Concéde…"), not text
    return c


def _canon(e) -> tuple[str, dict, str, dict] | None:
    t, d = e.type, e.data
    if t in STRUCTURAL:
        return None
    if t == "hymn":
        stanzas = d["stanzas"]
        flat = [ln for st in stanzas for ln in st]
        breaks, i = [], 0
        for st in stanzas[:-1]:
            i += len(st)
            breaks.append(i)
        return "hymn", {"stanzas": stanzas}, "\n".join(flat), {"breaks": breaks, "page_breaks": d.get("page_breaks", [])}
    if t == "ant":
        extra = {k: d[k] for k in ("num", "prefix", "repeat", "dagger", "lead", "bare") if d.get(k)}
        return "ant", {"text": d["text"]}, d["text"], extra
    if t == "psalm":
        lines, daggers, brk = [], [], {}
        for i, ln in enumerate(d.get("lines", [])):
            txt, dag = strip_dagger(ln["t"])
            if dag:
                daggers.append(i)
            if ln.get("brk"):
                brk[i] = ln["brk"]
            item = {"v": ln["v"], "t": txt, "x": ln["x"]}
            if ln.get("resp"):
                item["resp"] = True
            if ln.get("refrain"):
                item["refrain"] = True
            lines.append(item)
        if d.get("psalm"):
            otype = "psalm"
            ident = {"psalm": d["psalm"]["hebr"], "vulg": d["psalm"]["vulg"]}
        else:
            otype = "canticle"
            ident = {"ref": d.get("ref", ""), "gospel": bool(d.get("gospel"))}
        payload = {**ident, "lines": lines}
        for k in ("title", "epigraph"):
            if d.get(k):
                payload[k] = d[k]
        if d.get("no_gloria"):
            payload["no_gloria"] = True
        key = json.dumps(ident, sort_keys=True) + "\n" + "\n".join(f"{l['v'] or ''}|{l['x']}|{l['t']}" for l in lines)
        extra = {"head": [x for x in d.get("head", []) if x not in d.get("head_after", [])],
                 "head_after": d.get("head_after", []), "range": (d.get("psalm") or {}).get("range", ""),
                 "section": d.get("section", ""), "ant_slot": d.get("ant_slot", "")}
        if d.get("epigraph"):
            extra["epigraph"] = d["epigraph"]
        if daggers:
            extra["daggers"] = daggers
        if brk:
            extra["brk"] = brk
        if d.get("gloria_printed"):
            extra["gloria_printed"] = True
        return otype, payload, key, extra
    if t in ("versicle", "responsory", "resp_breve"):
        key = "\n".join(f"{k} {v}" for k, v in d["pairs"])
        extra = {"nosign": True} if d.get("nosign") else {}
        return t, {"pairs": d["pairs"], **({"ref": d["ref"]} if d.get("ref") else {})}, key + (d.get("ref") or ""), extra
    if t == "reading":
        paras = paragraphs(d["lines"])
        payload = {"intro": d["intro"], "meta": d["meta"], "lines": d["lines"], "ref": d.get("ref", "")}
        key = "\n".join(d["intro"] + d["meta"] + paras)
        return "reading", payload, key, {}
    if t in ("lectio_brevis", "oratio", "prayer", "text"):
        paras = paragraphs(d["lines"])
        payload = {"lines": d["lines"]}
        if d.get("ref"):
            payload["ref"] = d["ref"]
        return t, payload, (d.get("ref") or "") + "\n" + "\n".join(paras), {}
    if t == "te_deum":
        return "te_deum", {"lines": d["lines"]}, "\n".join(x for _, x in d["lines"]), {}
    if t == "preces":
        return "preces", d, json.dumps(d, ensure_ascii=False, sort_keys=True), {}
    if t in ("rubric", "link", "ordinary_ref"):
        txt = d.get("text", "")
        payload = {"text": txt}
        if t == "link":
            payload["slot"] = e.slot
        extra = {"target": d["target"]} if d.get("target") else {}
        return t, payload, f"{e.slot}|{txt}" if t == "link" else txt, extra
    if t == "unparsed":
        return "unparsed", {"text": e.source_text}, e.source_text, {}
    raise ValueError(f"no canonical form for element type {t}")


def object_id(otype: str, payload: dict, key: str) -> str:
    hh = h(key)
    if otype == "psalm":
        nums = unit_verses(payload["lines"])[0]
        rng = f"{nums[0]}-{nums[-1]}" if nums else "x"
        rng = re.sub(r"[^0-9a-z\-]", "", rng.replace(",", "_"))
        base = psalm_base(payload["psalm"])
        suffix = payload["psalm"][len(str(base)):].lower()
        return f"ps.{base:03d}{suffix}.{rng}.{hh[:4]}"
    if otype == "canticle":
        return f"cant.{canticle_slug(payload['ref'])}.{hh[:4]}"
    if otype in ("rubric", "link", "ordinary_ref", "unparsed"):
        return f"{PREFIX.get(otype, otype)}.{slug(payload.get('text', ''), 5)}.{hh[:4]}"
    first = {
        "hymn": lambda p: p["stanzas"][0][0],
        "ant": lambda p: p["text"],
        "versicle": lambda p: p["pairs"][0][1],
        "responsory": lambda p: p["pairs"][0][1],
        "resp_breve": lambda p: p["pairs"][0][1],
        "reading": lambda p: (p["lines"][0][1] if p["lines"] else " ".join(p["intro"])),
        "preces": lambda p: p.get("intro") or p.get("response", ""),
        "te_deum": lambda p: p["lines"][0][1],
    }.get(otype, lambda p: p["lines"][0][1])(payload)
    return f"{PREFIX[otype]}.{slug(first)}.{hh}"


def incipit(otype: str, payload: dict) -> str:
    if otype in ("psalm",):
        return f"Ps {payload['psalm']} ({payload['vulg']})"
    if otype == "canticle":
        return payload["ref"]
    oid = object_id(otype, payload, "")
    return oid.split(".")[1].replace("-", " ")


def plain_text(otype: str, payload: dict) -> str:
    """Full plain text of an object, for search and for the reference catalog."""
    if otype == "hymn":
        return " / ".join(plain(l) for st in payload["stanzas"] for l in st)
    if otype == "ant" or otype in ("rubric", "link", "ordinary_ref", "unparsed"):
        return plain(payload.get("text", ""))
    if otype in ("psalm", "canticle"):
        return " ".join(plain(l["t"]) for l in payload["lines"])
    if otype in ("versicle", "responsory", "resp_breve"):
        return " ".join(f"{k}. {plain(v)}" for k, v in payload["pairs"])
    if otype == "reading":
        return " ".join([plain(x) for x in payload["intro"] + payload["meta"]] + [plain(p) for p in paragraphs(payload["lines"])])
    if otype == "preces":
        parts = [plain(payload.get("intro", "")), plain(payload.get("response", ""))]
        if payload.get("response_alt"):
            parts.append(plain(payload["response_alt"]))
        parts += [f"{plain(p['a'])} — {plain(p['b'])}" for p in payload.get("petitions", [])]
        return " ".join(parts)
    if otype == "te_deum":
        return " ".join(plain(x) for _, x in payload["lines"])
    return " ".join(plain(p) for p in paragraphs(payload.get("lines", [])))


# ------------------------------------------------------------------------------------------------ round trip

def restore(otype: str, payload: dict, extra: dict, slot: str = "") -> str:
    """Rebuild the printed text (as joined source lines) from object payload + occurrence extra."""
    if extra.get("choice"):           # numbered alternative: "<n> text" (an antiphon without "Ant.")
        rest = {k: v for k, v in extra.items() if k != "choice"}
        body = payload["text"] if otype == "ant" else restore(otype, payload, rest, slot)
        return f"{extra['choice']} {body}"
    if otype == "hymn":
        return " ".join(l for st in payload["stanzas"] for l in st)
    if otype == "ant":
        head = "" if extra.get("bare") else (extra.get("lead") or "Ant.")   # lead "Vel:"; bare: no label (COM 1300)
        if extra.get("num"):
            head += f" {extra['num']}"
        if extra.get("prefix"):
            head += f" {extra['prefix']}"
        return f"{head} {payload['text']}" + (" †" if extra.get("dagger") else "")
    if otype in ("psalm", "canticle"):
        parts = list(extra.get("head", []))
        if extra.get("epigraph"):
            parts.append(extra["epigraph"])
        parts += extra.get("head_after", [])
        dag = set(extra.get("daggers", []))
        for i, l in enumerate(payload["lines"]):
            s = (f"{l['v']} " if l["v"] else "") + l["t"]
            parts.append(("† " if i in dag else "") + s)
        if extra.get("gloria_printed"):
            parts.append("Glória Patri et Fílio * et Spirítui Sancto. Sicut erat in princípio et nunc et semper * "
                          "et in sǽcula sæculórum. Amen.")
        return " ".join(parts)
    if otype in ("versicle", "responsory", "resp_breve"):
        if extra.get("nosign"):
            return " ".join(v for _, v in payload["pairs"])
        return " ".join(f"{'℣' if k == 'V' else '℟'}. {v}" for k, v in payload["pairs"])
    if otype == "reading":
        return " ".join(payload["intro"] + payload["meta"] + [t for _, t in payload["lines"]])
    if otype in ("lectio_brevis", "oratio", "prayer", "text"):
        return " ".join(t for _, t in payload["lines"])
    if otype == "te_deum":
        return " ".join(t for _, t in payload["lines"])
    if otype == "preces":
        parts = [payload.get("intro", ""), payload.get("response", "")]
        if payload.get("response_alt"):
            parts.append(payload["response_alt"])
        for p in payload.get("petitions", []):
            if p.get("alt"):
                parts.append("(vel:")
            parts += [p["a"], "— " + p["b"]]
        if payload.get("tail"):
            parts.append(payload["tail"])
        return " ".join(parts)
    return payload.get("text", "")


def cmp_key(s: str) -> str:
    """Comparison form: no tags, no whitespace (verse numbers kept). Strong but layout-insensitive."""
    return re.sub(r"\s+", "", TAG_RE.sub("", s))

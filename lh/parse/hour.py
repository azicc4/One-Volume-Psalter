"""L3: segment classified lines into hour instances and parse each hour into typed elements with slot codes.

Every source line ends up in exactly one element (unrecognised lines become `unparsed` elements, which the
verification step reports), so the parse is lossless and auditable back to PDF pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from lh.extract.lines import HOUR_HEADERS, SUBHOURS, Line, norm_space

LABELS = (
    "HYMNUS", "PSALMODIA", "LECTIO PRIOR", "LECTIO ALTERA", "LECTIO BREVIS", "RESPONSORIUM BREVE",
    "RESPONSORIUM", "CANTICUM EVANGELICUM", "PRECES",
)
ROMAN_RE = re.compile(r"^(?:[IVX]+)(?: \([A-Za-z]+\))?$")          # section numeral, e.g. "II", "XIX (Coph)"
PSALM_HEAD_RE = re.compile(r"^Psalmus (\d+)(?: ([AB]))?(?: \((\d+)(?: ([AB]))?\))?(?:, (.+))?$")
ANNO_RE = re.compile(r"^Anno ([ABC])$")
ALT_RE = re.compile(r"^(?:vel|aut)\b|^Ad libitum etiam", re.I)   # "Vel:", "Vel alia:", "vel de Communi…", "aut de die…"


@dataclass
class Element:
    type: str
    slot: str = ""
    sub: str = ""                 # TERCE / SEXT / NONE inside Hora media
    cond: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)
    lines: list[Line] = field(default_factory=list)

    @property
    def page(self) -> int:
        return self.lines[0].page if self.lines else 0

    @property
    def source_text(self) -> str:
        return " ".join(L.text for L in self.lines)

    def __repr__(self):
        s = f"{self.type}:{self.slot}" + (f"@{self.sub}" if self.sub else "") + (f" {self.cond}" if self.cond else "")
        return f"<{s} p{self.page} {self.source_text[:70]!r}>"


@dataclass
class Hour:
    pdf: str
    section: str                  # last 20.2pt heading, e.g. "HEBDOMADA I"
    day: str                      # day title (16.6pt), lines joined with " / "
    day_extra: list[str]          # lines between day title and first hour (rank, occasion, bio…)
    title: str                    # "Ad Laudes matutinas"
    code: str                     # LAUDS
    subtitle: str = ""
    lines: list[Line] = field(default_factory=list)
    elements: list[Element] = field(default_factory=list)

    @property
    def page_start(self):
        return self.lines[0].page

    @property
    def page_end(self):
        return self.lines[-1].page

    def __repr__(self):
        return f"<Hour {self.pdf} {self.section} | {self.day} | {self.code} p{self.page_start}-{self.page_end}>"


# --------------------------------------------------------------------------------------------- segmentation

@dataclass
class Outside:
    """A line that belongs to no hour: a heading, a day's preamble (rank, occasion, biography) or front matter."""
    line: Line
    role: str          # heading | day_extra | front
    section: str
    day: str


def segment(lines: list[Line], pdf: str) -> tuple[list[Hour], list[Outside]]:
    """Split the line stream into hour instances. Returns (hours, lines outside any hour, with their role)."""
    hours: list[Hour] = []
    outside: list[Outside] = []
    section, day, day_extra = "", "", []
    cur: Hour | None = None
    prev_kind = ""
    for L in lines:
        k = L.kind
        if k == "week":
            section = f"{section} {L.text}" if prev_kind == "week" else L.text   # wrapped 20pt heading
            cur = None
            outside.append(Outside(L, "heading", section, day))
        elif k == "day":
            day = f"{day} / {L.text}" if prev_kind == "day" else L.text
            day_extra = []
            cur = None
            outside.append(Outside(L, "heading", section, day))
        elif k == "hour":
            cur = Hour(pdf, section, day, list(day_extra), L.text, HOUR_HEADERS[L.text], lines=[L])
            hours.append(cur)
        elif cur is None:
            if day:
                day_extra.append(L.text)
            outside.append(Outside(L, "day_extra" if day else "front", section, day))
        else:
            cur.lines.append(L)
        prev_kind = k
    return hours, outside


# --------------------------------------------------------------------------------------------- markup helpers

def markup(L: Line, skip_first: bool = False) -> str:
    """Inline markup for a line: <v>n</v> verse numbers, <r>…</r> red, <i>…</i> italic."""
    out = ["<r>†</r> "] if L.lead_dagger else []
    runs = L.runs[1:] if skip_first else L.runs
    for r in runs:
        t = r.text
        if not t:
            continue
        if r.verse_no:
            out.append(f"<v>{t.strip()}</v> ")
        elif r.red and r.italic:
            out.append(f"<r><i>{t}</i></r>")
        elif r.red:
            out.append(f"<r>{t}</r>")
        elif r.italic:
            out.append(f"<i>{t}</i>")
        else:
            out.append(t)
    s = norm_space("".join(out))
    s = re.sub(r"</(i|r)>\s*<\1>", " ", s)  # merge adjacent same tags split by spaces
    return s


def xclass(L: Line) -> int:
    """0 = flush left (72), 1 = indented paragraph start (~94), 2 = continuation / hanging (>= 100)."""
    if L.x0 < 85:
        return 0
    if L.x0 < 99:
        return 1
    return 2


def numbered(L: Line) -> str | None:
    """'1 Concéde nos…': a red number before black text = one of several numbered alternatives (BVM on Saturday)."""
    if L.kind == "rubric" and len(L.runs) > 1 and L.runs[0].red and not L.runs[1].red:
        m = re.fullmatch(r"\s*(\d+)\s*", L.runs[0].text)
        return m.group(1) if m else None
    return None


def label_parts(text: str) -> tuple[str, str]:
    for lab in LABELS:
        if text.startswith(lab):
            return lab, text[len(lab):].strip()
    return text, ""


# --------------------------------------------------------------------------------------------- element parser

class HourParser:
    def __init__(self, hour: Hour):
        self.h = hour
        self.L = hour.lines
        self.i = 1                  # skip the hour header line
        self.els: list[Element] = []
        self.section = ""           # current label section
        self.sub = ""
        self.cond: dict = {}        # pending condition for the next content element
        self.psalm_no = 0           # running psalm-unit counter within the psalmody
        self.cur_ant: Element | None = None
        self.ants_seen: dict = {}
        self.last_psalm: Element | None = None
        self.after_psalmody = False
        self.alt_ref = ""           # citation of an alternative short reading: "Vel (Ap 12, 1):"

    # -- helpers
    def peek(self, j=0) -> Line | None:
        k = self.i + j
        return self.L[k] if k < len(self.L) else None

    def emit(self, type_, lines, slot="", data=None, keep_cond=False) -> Element:
        e = Element(type_, slot, self.sub, dict(self.cond), data or {}, lines)
        if not keep_cond and type_ not in ("rubric", "label", "marker"):
            # conditions apply to the next content element only (year A/B/C, alternatives)
            year = self.cond.get("year")
            self.cond = {"year": year} if (year and type_ != "ant") else {}
        self.els.append(e)
        return e

    def last_content(self) -> Element | None:
        return next((e for e in reversed(self.els) if e.type not in ("rubric", "label", "marker")), None)

    def dash_ahead(self) -> bool:
        """Does the text block starting here contain preces second halves ("— …")?"""
        for X in self.L[self.i:]:
            if X.kind == "dash":
                return True
            if X.kind not in ("text", "italic") or X.text == "Pater noster.":
                return False
        return False

    def take_while(self, pred) -> list[Line]:
        out = []
        while self.i < len(self.L) and pred(self.L[self.i]):
            out.append(self.L[self.i])
            self.i += 1
        return out

    # -- main loop
    def parse(self) -> list[Element]:
        h = self.h
        if len(self.L) > 1 and self.L[1].kind == "subtitle":
            h.subtitle = self.L[1].text
            self.emit("marker", [self.L[1]], "SUBTITLE", {"text": self.L[1].text}, keep_cond=True)
            self.i = 2
        while self.i < len(self.L):
            L = self.L[self.i]
            k, t = L.kind, L.text
            if k == "subtitle":
                self.i += 1
                self.emit("marker", [L], "SUBTITLE", {"text": t}, keep_cond=True)
            elif k in ("day", "week", "hour"):
                self.i += 1   # extra heading line inside an appendix chapter (e.g. 2nd line of a two-line title)
                self.emit("marker", [L], "HEADING", {"text": t}, keep_cond=True)
            elif k == "subhour":
                self.i += 1
                self.sub = SUBHOURS.get(t, t)
                self.emit("marker", [L], "SUBHOUR", {"text": t}, keep_cond=True)
                if self.after_psalmody and self.section in ("PSALMODIA", "HYMNUS"):
                    self.section = ""  # per-hour closing section of Hora media
            elif k == "label":
                self.i += 1
                lab, ref = label_parts(t)
                if self.section == "PSALMODIA" and lab != "PSALMODIA":
                    self.after_psalmody = True
                self.section = lab
                if lab == "PSALMODIA" and self.h.code == "MIDDAY":
                    self.sub = ""      # Hora media psalmody is shared by Terce, Sext and None
                self.emit("label", [L], lab, {"label": lab, "ref": ref}, keep_cond=True)
            elif k == "rubric_c" and t == "Oratio":
                self.i += 1
                self.section = "ORATIO"
                if self.section_was_psalmody():
                    self.after_psalmody = True
                self.emit("label", [L], "ORATIO", {"label": "Oratio"}, keep_cond=True)
            elif re.match(r"^Hymnus Te Deum", t):
                self.i += 1
                self.section = "TE DEUM"
                self.emit("label", [L], "TE_DEUM", {"label": t}, keep_cond=True)
            elif ANNO_RE.match(t):
                self.i += 1
                self.cond["year"] = ANNO_RE.match(t).group(1)
                self.emit("marker", [L], "YEAR", {"year": self.cond["year"]}, keep_cond=True)
            elif k == "ant":
                self.parse_ant()
            elif k == "text" and t.startswith("Deus, in adiutórium") and not self.section:
                self.i += 1   # opening printed without its ℣ sign (source quirk, e.g. PA 277)
                self.emit("versicle", [L], "OPENING", {"pairs": [["V", markup(L)]], "nosign": True})
            elif k == "rubric_c" or (k == "rubric" and self.section in ("PSALMODIA", "CANTICUM EVANGELICUM")
                                     and PSALM_HEAD_RE.match(t)):
                self.parse_psalm_or_meta()
            elif k == "verse" and self.section in ("PSALMODIA", "CANTICUM EVANGELICUM", "") and self.last_psalm:
                self.parse_psalm_body(self.last_psalm, continuing=True)
            elif k in ("V", "R"):
                self.parse_vr()
            elif self.section in ("CANTICUM EVANGELICUM", "ORATIO") and numbered(L):
                self.parse_numbered()
            elif k == "rubric":
                self.i += 1
                self.parse_rubric(L)
            elif k == "link":
                self.i += 1
                self.parse_link(L)
            elif k in ("text", "italic", "verse"):
                self.parse_text_block()
            else:
                self.i += 1
                self.emit("unparsed", [L], data={"why": f"kind {k} in section {self.section!r}"})
        return self.els

    def section_was_psalmody(self):
        return any(e.slot.startswith("PS") for e in self.els)

    # -- antiphons
    def parse_ant(self):
        first = self.L[self.i]
        self.i += 1
        cont = self.take_while(lambda L: L.kind in ("text", "italic") and xclass(L) == 0 and not L.block_start)
        if not cont:
            # page-break continuation: next page starts flush-left with lowercase or punctuation-led text
            nxt = self.peek()
            if nxt and nxt.page_top and nxt.kind == "text" and xclass(nxt) == 0 and nxt.text[:1].islower():
                cont = [nxt]
                self.i += 1
        lines = [first] + cont
        red = first.runs[0].text.strip()
        m = re.match(r"Ant\.\s*(\d)?\s*(.*)$", red)
        num = m.group(1) if m else None
        prefix = (m.group(2) if m else "").strip()
        text = norm_space(" ".join([markup(first, skip_first=True)] + [markup(L) for L in cont]))
        data = {"num": num, "text": text}
        m2 = re.search(r"\s*<r>\s*†\s*</r>$", text)
        if m2:
            data["text"] = text = text[:m2.start()].rstrip()
            data["dagger"] = True
        if prefix:
            data["prefix"] = prefix
        prior = self.ants_seen.get((self.section, self.sub, text))
        repeat = prior is not None and (num is None or num == prior.data["num"])
        if self.section == "CANTICUM EVANGELICUM":
            slot = "GOSPEL_ANT"
        elif self.h.code == "INV":
            slot = "INV_ANT"
        elif self.section == "HYMNUS" and self.sub:
            slot = "ANT"          # seasonal Hora media: per-hour antiphon after the hymn
        elif self.section in ("PSALMODIA",) or self.h.code in ("MIDDAY",):
            slot = f"ANT{num}" if num else "ANT"
        else:
            slot = "ANT"
        if repeat:
            data["repeat"] = True
            e = self.emit("ant", lines, prior.slot + "_R", data, keep_cond=True)
            e.cond = dict(prior.cond)
        else:
            e = self.emit("ant", lines, slot, data)
            self.cur_ant = e
            self.ants_seen[(self.section, self.sub, text)] = e

    def parse_numbered(self):
        """Numbered alternatives ("Antiphona ex sequentibus ad libitum sumitur: 1 … 6 …"): Gospel antiphons or
        prayers. The number is printed, not part of the text: kept as data/extra "choice" and cond {"choice": n}."""
        first = self.L[self.i]
        num = numbered(first)
        self.i += 1
        cont = self.take_while(lambda X: X.kind == "text" and xclass(X) == 0 and not X.block_start)
        lines = [first] + cont
        if self.section == "ORATIO":
            data = {"lines": [[xclass(first), markup(first, skip_first=True)]] + [[xclass(X), markup(X)] for X in cont],
                    "choice": num}
            e = self.emit("oratio", lines, "ORATIO", data)
        else:
            text = norm_space(" ".join([markup(first, skip_first=True)] + [markup(X) for X in cont]))
            data = {"num": None, "text": text, "choice": num}
            prior = self.ants_seen.get((self.section, self.sub, text))
            if prior is not None:
                data["repeat"] = True
                e = self.emit("ant", lines, "GOSPEL_ANT_R", data, keep_cond=True)
            else:
                e = self.emit("ant", lines, "GOSPEL_ANT", data)
                self.cur_ant = self.ants_seen[(self.section, self.sub, text)] = e
        e.cond = {**e.cond, "choice": num}

    # -- psalms, canticles, and centred meta lines
    def parse_psalm_or_meta(self):
        L = self.L[self.i]
        t = L.text
        head = []
        is_psalm = bool(PSALM_HEAD_RE.match(t)) or t == "Canticum" or ROMAN_RE.match(t) or (
            self.section == "CANTICUM EVANGELICUM" and re.match(r"^Lc \d", t))
        if not is_psalm:
            # centred red line outside psalmody: reading refs/titles are handled in parse_text_block;
            # here it's a free-standing rubric (e.g. a title inside a reading section)
            self.i += 1
            self.emit("rubric", [L], data={"text": markup(L), "centered": True}, keep_cond=True)
            return
        head = []
        while self.i < len(self.L):
            X = self.L[self.i]
            if X.kind == "rubric_c" and X.text != "Oratio":
                head.append(X)
            elif X.kind == "rubric" and head and not X.block_start and X.block == head[-1].block:
                head.append(X)          # wrapped title line
            else:
                break
            self.i += 1
        heads = [X.text for X in head]   # long titles are set flush-left (not centred) but are separate lines
        data: dict = {"head": heads}
        inherit = None
        if ROMAN_RE.match(heads[0]):
            # section continuation of the previous psalm (heading not repeated)
            inherit = self.last_psalm
            data["section"] = heads[0]
            if inherit is not None:
                for k in ("psalm", "canticle", "ref", "title"):
                    if k in inherit.data:
                        data[k] = inherit.data[k]
        else:
            m = PSALM_HEAD_RE.match(heads[0])
            if m:
                vul, va, heb, ha, rng = m.groups()
                if heb:   # "Psalmus 9 A (9)", "Psalmus 18 B (19 B)", "Psalmus 114 (116 A)"
                    hebr = heb + (ha or "")
                else:     # same number in both systems: "Psalmus 6", "Psalmus 149"
                    hebr = vul + (va or "")
                data["psalm"] = {"vulg": vul + (va or ""), "hebr": hebr, "range": rng or ""}
                rest = heads[1:]
            elif heads[0] == "Canticum":
                data["canticle"] = True
                data["ref"] = heads[1] if len(heads) > 1 else ""
                rest = heads[2:]
            else:  # Gospel canticle: "Lc 1, 68-79"
                data["canticle"] = True
                data["gospel"] = True
                data["ref"] = heads[0]
                rest = heads[1:]
            for x in rest:
                if ROMAN_RE.match(x):
                    data["section"] = x
                elif "title" not in data:
                    data["title"] = x
                else:
                    data.setdefault("extra", []).append(x)
        # epigraph (italic sentence + citation, possibly wrapped)
        epi = []
        nxt = self.peek()
        if nxt and nxt.kind == "italic":
            epi = [nxt]
            self.i += 1
            while True:
                j = " ".join(X.text for X in epi)
                nxt = self.peek()
                unclosed = j.count("(") > j.count(")")
                ended = re.search(r"\)\.?$|\.$", j) and not unclosed
                if ended or not nxt or nxt.kind not in ("text", "italic") or nxt.verse:
                    break
                epi.append(nxt)
                self.i += 1
            data["epigraph"] = norm_space(" ".join(markup(X) for X in epi))
        # a section numeral may follow the epigraph
        nxt = self.peek()
        after = []
        if nxt and nxt.kind == "rubric_c" and ROMAN_RE.match(nxt.text):
            data["section"] = nxt.text
            data["head_after"] = [nxt.text]     # printed after the epigraph
            after = [nxt]
            self.i += 1
        self.psalm_no += 1
        slot = "GOSPEL_CANT" if data.get("gospel") else f"PS{self.psalm_no}"
        e = self.emit("psalm", head + epi + after, slot, data)
        if self.cur_ant is not None and slot != "GOSPEL_CANT":
            e.data["ant_slot"] = self.cur_ant.slot
        self.last_psalm = e
        self.parse_psalm_body(e)

    def parse_psalm_body(self, e: Element, continuing=False):
        verses = e.data.setdefault("lines", [])
        while self.i < len(self.L):
            L = self.L[self.i]
            if L.kind == "verse" or (L.kind in ("text", "italic") and not re.match(r"^Glória Patri et Fílio", L.text)
                                      and not ANNO_RE.match(L.text) and L.text != "Pater noster."):
                v = L.verse
                brk = None
                if L.block_start and verses:
                    brk = "page" if L.page_top else "block"
                verses.append({"v": v, "t": markup(L, skip_first=bool(v)), "x": xclass(L), **({"brk": brk} if brk else {})})
                e.lines.append(L)
                self.i += 1
            elif L.kind == "rubric" and re.match(r"^\((?:Proponitur et repetitur|Repetitur) antiphona\)$", L.text):
                verses.append({"v": None, "t": markup(L), "x": xclass(L), "refrain": True})
                e.lines.append(L)
                self.i += 1
            elif L.kind in ("R", "rubric") and re.match(r"^\(?\s*℟\. Allelúia", L.text):
                verses.append({"v": None, "t": markup(L), "x": xclass(L), "resp": True})
                e.lines.append(L)
                self.i += 1
            elif re.match(r"^Glória Patri et Fílio", L.text):
                glo = [L] + self.L[self.i + 1:self.i + 4]
                e.data["gloria_printed"] = True
                e.lines.extend(glo)
                self.i += len(glo)
            else:
                break

    # -- versicles / responsories
    def parse_vr(self):
        lines = []
        pairs = []
        while self.i < len(self.L):
            L = self.L[self.i]
            if L.kind in ("V", "R"):
                pairs.append([L.kind, markup(L, skip_first=True)])
                lines.append(L)
                self.i += 1
            elif L.kind == "text" and pairs and xclass(L) == 0 and (not L.block_start or L.page_top):
                pairs[-1][1] = norm_space(pairs[-1][1] + " " + markup(L))
                lines.append(L)
                self.i += 1
            else:
                break
        text0 = pairs[0][1] if pairs else ""
        if self.section in ("RESPONSORIUM", "RESPONSORIUM BREVE"):
            prev = [e for e in self.els if e.type == "reading"]
            if self.section == "RESPONSORIUM":
                slot = "RESP2" if prev and prev[-1].slot == "LECT2" else "RESP1"
                typ = "responsory"
            else:
                slot, typ = "RB", "resp_breve"
            self.emit(typ, lines, slot, {"pairs": pairs})
            self.section = ""
            return
        if text0.startswith("Deus, in adiutórium") or text0.startswith("Dómine, lábia"):
            slot = "OPENING"
        elif self.h.code == "OR" and self.section == "PSALMODIA":
            slot = "OR_VERSE"
        elif self.h.code == "COMPLINE" and text0.startswith("Noctem"):
            slot = "BLESSING"
        elif self.section == "LECTIO BREVIS":
            slot = "V"
        else:
            slot = "VR"
        self.emit("versicle", lines, slot, {"pairs": pairs})

    # -- rubrics and links
    def parse_rubric(self, L: Line):
        t = L.text
        # wrapped rubric lines continue at x=72 in the same block
        lines = [L] + self.take_while(lambda X: X.kind == "rubric" and not X.block_start)
        text = norm_space(" ".join(markup(X) for X in lines))
        plain = norm_space(" ".join(X.text for X in lines))
        if ALT_RE.match(plain):
            self.cond["alt"] = plain
            # an alternative printed without its label: a short reading after the short responsory ("Vel (Ap 12, 1):"),
            # or another reading after a responsory ("Vel alia:", "aut de die 16 iulii:")
            prev = self.last_content()
            m = re.match(r"^Vel \((.+)\):$", plain)
            if m and prev is not None and prev.slot == "RB":
                self.section, self.alt_ref = "LECTIO BREVIS", m.group(1)
            elif prev is not None and prev.slot in ("RESP1", "RESP2") and not self.section:
                self.section = "LECTIO PRIOR" if prev.slot == "RESP1" else "LECTIO ALTERA"
        elif re.match(r"^I+\. Quando Officium lectionis", plain):
            self.cond["variant"] = "night" if plain.startswith("I.") else "day"
        elif "non dicitur Glória Patri" in plain or "non dicitur Gloria Patri" in plain:
            if self.last_psalm is not None:
                self.last_psalm.data["no_gloria"] = True
        self.emit("rubric", lines, "", {"text": text}, keep_cond=True)

    def parse_link(self, L: Line):
        more = self.take_while(lambda X: X.kind in ("rubric", "rubric_c") and X.block == L.block and not X.block_start)
        t = norm_space(" ".join([L.text] + [X.text for X in more]))
        if more:
            self.emit("link", [L] + more, "SUBST" if "Invitatori" in t else "LINK", {"text": t, "target": L.link},
                      keep_cond=True)
            return
        if t.startswith("Conclusio"):
            slot = "CONCLUSION"
        elif t == "Vel alter" or (t.startswith("Ad libitum") and self.section == "HYMNUS"):
            slot = "HYMN_ALT"     # alternative hymn printed elsewhere ("Ad libitum dici potest hymnus Dies iræ.")
        elif t.startswith("Antiphonæ finales"):
            slot = "MARIAN"
        elif t.startswith("Memoria ad libitum"):
            slot = "MEMORIAL"     # where the optional memorial (BVM on Saturday) takes over
        elif self.section in ("LECTIO PRIOR", "LECTIO ALTERA") and re.match(r"^(?:Ex|De) ", t):
            slot = "LECT1" if self.section == "LECTIO PRIOR" else "LECT2"    # reading given by reference
        elif self.h.code == "INV":
            slot = "INV_PSALM"
        elif t.startswith("Ad alias Horas"):
            slot = "COMPLEMENTARY"
        else:
            slot = "LINK"
        self.emit("link", [L], slot, {"text": t, "target": L.link}, keep_cond=slot in ("INV_PSALM",))

    # -- prose / poetry blocks (hymns, readings, prayers, preces, Te Deum)
    def parse_text_block(self):
        sec = self.section
        if sec == "HYMNUS":
            lines = self.take_while(lambda X: X.kind in ("text", "italic"))
            stanzas: list[list[str]] = []
            for X in lines:
                if X.block_start or not stanzas:
                    stanzas.append([])
                stanzas[-1].append(markup(X))
            breaks = ["page" if X.page_top else "block" for X in lines if X.block_start][1:] if lines else []
            self.emit("hymn", lines, "HYMN", {"stanzas": stanzas, "page_breaks": [i for i, X in enumerate(
                [Y for Y in lines if Y.block_start]) if X.page_top and i > 0]})
            return
        if sec == "PRECES":
            self.parse_preces()
            return
        if sec == "TE DEUM":
            lines = self.take_while(lambda X: X.kind in ("text", "italic", "rubric") and X.text != "Oratio")
            self.emit("te_deum", lines, "TE_DEUM", {"lines": [[X.kind, markup(X)] for X in lines]})
            self.section = ""
            return
        if sec in ("LECTIO PRIOR", "LECTIO ALTERA"):
            self.parse_reading(sec)
            return
        if self.dash_ahead():
            # preces without their PRECES label (LQP 2522) or resumed after an interruption ("Vel aliæ:", PA 6277)
            self.parse_preces()
            return
        lines = self.take_while(lambda X: X.kind in ("text", "italic") and X.text != "Pater noster.")
        if not lines:  # e.g. "Pater noster." alone
            L = self.L[self.i]
            self.i += 1
            self.emit("ordinary_ref", [L], "PATER" if L.text == "Pater noster." else "TEXT", {"text": L.text})
            return
        data = {"lines": [[xclass(X), markup(X)] for X in lines]}
        if sec == "LECTIO BREVIS":
            if self.alt_ref:
                data["ref"], self.alt_ref = self.alt_ref, ""
            self.emit("lectio_brevis", lines, "LB", data)
        elif sec == "ORATIO":
            self.emit("oratio", lines, "ORATIO", data)
            self.section = ""
        elif self.h.code == "INV" and not any(e.type == "versicle" for e in self.els):
            self.emit("prayer", lines, "PREP_PRAYER", data)
        else:
            self.emit("text", lines, "TEXT", data)

    def parse_reading(self, sec):
        """LECTIO PRIOR / ALTERA: intro line(s), centred refs/title, then paragraphs up to the next label."""
        lines = []
        while self.i < len(self.L):
            X = self.L[self.i]
            if X.kind in ("label", "hour", "subhour", "link") or (X.kind == "rubric_c" and X.text == "Oratio"):
                break
            if X.kind in ("V", "R", "ant", "dash"):
                break
            lines.append(X)
            self.i += 1
        intro, meta, body = [], [], []
        for X in lines:
            if not body and (X.kind == "rubric_c" or (X.kind == "rubric" and X.runs[0].italic)):
                meta.append(markup(X))        # source citation / title (centred red, or italic red if long)
            elif not body and not meta and X.kind in ("text", "italic", "rubric") and xclass(X) == 0:
                intro.append(markup(X))       # "Incipit liber …" / "Ex Epístola sancti …" (flush left)
            else:
                body.append([xclass(X), markup(X)])
        self.emit("reading", lines, "LECT1" if sec == "LECTIO PRIOR" else "LECT2",
                  {"intro": intro, "meta": meta, "lines": body})

    def parse_preces(self):
        intro, response, petitions, lines = [], "", [], []
        first_half: list[str] = []
        alt = False
        while self.i < len(self.L):
            X = self.L[self.i]
            if X.kind == "text" and X.text == "Pater noster.":
                break
            if X.kind == "italic" and not response:
                response = markup(X)
            elif X.kind == "rubric" and X.text.strip().lower().startswith("(vel"):
                alt = True                       # the next petition is an alternative to the previous one
            elif X.kind == "dash":
                pet = {"a": norm_space(" ".join(first_half)), "b": markup(X, skip_first=True)}
                if alt:
                    pet["alt"] = True
                    alt = False
                petitions.append(pet)
                first_half = []
            elif X.kind == "text" and xclass(X) == 2 and petitions and not first_half and X.text[:1].islower():
                petitions[-1]["b"] = norm_space(petitions[-1]["b"] + " " + markup(X))   # wrapped second half
            elif X.kind in ("text", "italic") and not response:
                intro.append(markup(X))
            elif X.kind in ("text", "italic"):
                first_half.append(markup(X))
            else:
                break
            lines.append(X)
            self.i += 1
        data = {"intro": norm_space(" ".join(intro)), "response": response, "petitions": petitions}
        if first_half:
            data["tail"] = norm_space(" ".join(first_half))
        self.emit("preces", lines, "PRECES", data)
        self.section = ""


def parse_hour(hour: Hour) -> Hour:
    hour.elements = HourParser(hour).parse()
    return hour

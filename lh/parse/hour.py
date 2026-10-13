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
# Easter Vigil in place of the Office of Readings of Easter Sunday (GILH 212; LQP 1192-1198): numbered readings, each
# followed by its chant and prayer. Only LQP prints these labels.
VIGIL_READINGS = {"LECTIO PRIMA": "LECT1", "LECTIO SECUNDA": "LECT2", "LECTIO TERTIA": "LECT3", "LECTIO QUARTA": "LECT4"}
ROMAN_RE = re.compile(r"^(?:[IVX]+)(?: \([A-Za-z]+\))?$")          # section numeral, e.g. "II", "XIX (Coph)"
PSALM_HEAD_RE = re.compile(r"^Psalmus (\d+)(?: ([AB]))?(?: \((\d+)(?: ([AB]))?\))?(?:, (.+))?$")
# "Canticum" alone (reference on the next line), numbered "Canticum I" (ADV 8416, vigil canticles) or with the
# reference on the same line "Canticum Eph 1, 3-10" (ADV 286, Immaculate Conception Vespers)
CANT_HEAD_RE = re.compile(r"^Canticum(?: ([IVX]+|[1-4]? ?[A-Z][a-z]+ \d.*))?$")
ANNO_RE = re.compile(r"^Anno ([ABC])$")
ALT_RE = re.compile(r"^(?:vel|aut)\b|^Ad libitum etiam", re.I)   # "Vel:", "Vel alia:", "vel de Communi…", "aut de die…"
# Sanctis / Commons parser refinements (see is_inline_alt_ant, parse_ant, parse_rubric); ADV opted in by WS1: its
# Epiphany Complines print "Vel, si … dominica:" alternative orations (ADV 1090, 1117 …)
SANCTIS_SOURCES = {"SPA", "SP", "SQ", "SADV", "COM", "ADV"}
# complementary psalmody substitutes (COM 1684-1693; SP/SQ/SADV/SPA appendices), red heading + blue link:
# "Psalmus 126 (127) vel 130 (131)"
PSALM_VEL_RE = re.compile(r"^(Psalmus \d+ \(\d+\)),? vel (\d+ \(\d+\))$")
# Sub-variant rubrics (Commons, Office of the Dead): the following text applies only to one kind of saint or occasion,
# e.g. "Pro papa:", "Pro pluribus pastoribus:", "Vel alia, præsertim pro episcopo:", "In ipsa ecclesia dedicata:",
# "Tempore Adventus:". They become cond = {"for": "Pro papa"} on the element(s) they introduce.
SUBVAR_RE = re.compile(r"^(?:(?:Vel )?[Aa]lia, )?((?:præsertim )?[Pp]ro (?!precibus|vigilia)[^:.;]{2,60}"
                       r"|In ipsa ecclesia dedicata|Extra ipsam ecclesiam dedicatam|Tempore [A-Z][a-zæ]+)(?::|$)")
# rubrics introducing an alternative to the item just completed: reopen that item's section (see reopen_section)
ALT_REOPEN_RE = re.compile(r"^(?:Vel(?::| ali[aæ]\b)|Ubi vigilia protrahitur:)")


def subvariant(text: str) -> str | None:
    """'Pro papa:' → 'Pro papa'; 'Vel alia, præsertim pro episcopo:' → 'Præsertim pro episcopo'; else None."""
    m = SUBVAR_RE.match(norm_space(text))
    if not m:
        return None
    v = m.group(1).strip()
    return v[:1].upper() + v[1:]


def is_stanza_no(L: Line) -> bool:
    """A hymn stanza that starts with a red stanza number ('1 Qui lacrimátus Lázarum', SPA 1784)."""
    return len(L.runs) > 1 and L.runs[0].red and L.runs[0].text.strip().isdigit() and not L.runs[1].red


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


def _pretitle_enabled(pdf: str) -> bool:
    try:
        from lh.sources import plugin
        return bool(getattr(plugin(pdf), "PRE_TITLE_LINES", False))
    except (KeyError, ImportError):
        return False


def _n_pretitle(lines: list[Line], day_line: Line) -> int:
    """Number of trailing lines that are a centred date/occasion printed at the top of the day title's page
    ("Die 25 decembris", "Dominica infra octavam Nativitatis", ADV 713/1919): they belong to the next day."""
    n = 0
    for X in reversed(lines):
        if X.page == day_line.page and X.kind in ("text", "subhour") and X.x0 > 150:
            n += 1
        else:
            break
    return n if n and lines[-n].page_top else 0


def segment(lines: list[Line], pdf: str) -> tuple[list[Hour], list[Outside]]:
    """Split the line stream into hour instances. Returns (hours, lines outside any hour, with their role)."""
    hours: list[Hour] = []
    outside: list[Outside] = []
    section, day, day_extra = "", "", []
    cur: Hour | None = None
    prev_kind = ""
    pretitle = _pretitle_enabled(pdf)     # source plug-in opts in (PRE_TITLE_LINES = True)
    for L in lines:
        k = L.kind
        if k == "week":
            section = f"{section} {L.text}" if prev_kind == "week" else L.text   # wrapped 20pt heading
            cur = None
            outside.append(Outside(L, "heading", section, day))
        elif k == "day":
            pre: list[Line] = []
            if pretitle and prev_kind != "day":
                if cur is not None:                 # absorbed at the end of the previous hour
                    n = _n_pretitle(cur.lines[1:], L)
                    if n:
                        pre = cur.lines[-n:]
                        del cur.lines[-n:]
                else:                               # after a section heading: recorded as the previous day's preamble
                    n = _n_pretitle([o.line for o in outside], L)
                    if n:
                        pre = [o.line for o in outside[-n:]]
                        del outside[-n:]
            day = f"{day} / {L.text}" if prev_kind == "day" else L.text
            day_extra = [X.text for X in pre]
            cur = None
            outside += [Outside(X, "day_extra", section, day) for X in pre]
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


def hymn_data(lines: list[Line]) -> dict:
    """Stanzas (a stanza starts at a block start; page-top block starts are listed in page_breaks)."""
    stanzas: list[list[str]] = []
    for X in lines:
        if X.block_start or not stanzas:
            stanzas.append([])
        stanzas[-1].append(markup(X))
    return {"stanzas": stanzas, "page_breaks": [i for i, X in enumerate(
        [Y for Y in lines if Y.block_start]) if X.page_top and i > 0]}


def label_parts(text: str) -> tuple[str, str]:
    if text == "LECTIO" or text.startswith("LECTIO ("):
        return "LECTIO", text[6:].strip()     # the single reading of a commemoration (SADV 143)
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
        self.hymn_in_sub = False    # Hora media layout C (per-hour hymn + psalmody, e.g. SP 31): keep `sub`

    # -- helpers
    def peek(self, j=0) -> Line | None:
        k = self.i + j
        return self.L[k] if k < len(self.L) else None

    def emit(self, type_, lines, slot="", data=None, keep_cond=False) -> Element:
        e = Element(type_, slot, self.sub, dict(self.cond), data or {}, lines)
        if not keep_cond and type_ not in ("rubric", "label", "marker"):
            # conditions apply to the next content element only (year A/B/C, alternatives)
            year = self.cond.get("year")
            keep = {"year": year} if (year and type_ != "ant") else {}
            if type_ == "reading" and self.cond.get("for"):
                # a sub-variant reading ("Pro presbytero:") keeps its condition for its responsory
                keep.update({k: self.cond[k] for k in ("for", "alt") if k in self.cond})
            self.cond = keep
        self.els.append(e)
        return e

    def last_content(self) -> Element | None:
        return next((e for e in reversed(self.els) if e.type not in ("rubric", "label", "marker")), None)

    def dash_ahead(self) -> bool:
        """Does the text block starting here contain preces second halves ("— …")?"""
        prev = None
        for X in self.L[self.i:]:
            if X.kind == "dash":
                return True
            if X.kind == "rubric" and X.text.startswith("Vel:") and prev is not None and prev.kind == "italic":
                prev = X                    # alternative response after the italic response (SP 288, SA 124)
                continue
            prev = X
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
                more = []
                if t.count("(") > t.count(")"):      # reference wrapped onto a red line ("… Eccli 44, 16. / 17)", SPA 1946)
                    more = self.take_while(lambda X: X.kind == "rubric" and X.block == L.block and len(X.text) < 40)
                    t = norm_space(" ".join([t] + [X.text for X in more]))
                lab, ref = label_parts(t)
                if self.section == "PSALMODIA" and lab != "PSALMODIA":
                    self.after_psalmody = True
                self.section = lab
                if lab == "HYMNUS":
                    self.hymn_in_sub = bool(self.sub)   # layout C: "Ad Tertiam" precedes its own HYMNUS label
                if lab == "PSALMODIA" and self.h.code == "MIDDAY" and not self.hymn_in_sub:
                    self.sub = ""      # Hora media psalmody is shared by Terce, Sext and None
                self.emit("label", [L] + more, lab, {"label": lab, "ref": ref}, keep_cond=True)
            elif k == "rubric_c" and t == "Oratio":
                self.i += 1
                self.section = "ORATIO"
                if self.section_was_psalmody():
                    self.after_psalmody = True
                self.emit("label", [L], "ORATIO", {"label": "Oratio"}, keep_cond=True)
            elif re.match(r"^(?:In sollemnitatibus et festis )?Hymnus Te Deum", t):   # the long form: Communia
                self.i += 1
                self.section = "TE DEUM"
                self.emit("label", [L], "TE_DEUM", {"label": t}, keep_cond=True)
            elif ANNO_RE.match(t):
                self.i += 1
                self.cond["year"] = ANNO_RE.match(t).group(1)
                self.emit("marker", [L], "YEAR", {"year": self.cond["year"]}, keep_cond=True)
            elif k == "ant":
                self.parse_ant()
            elif (k == "text" and self.section == "CANTICUM EVANGELICUM" and self.els
                  and self.els[-1].slot == "YEAR"):
                self.parse_ant(bare=True)   # Gospel antiphon for one year printed without "Ant." (ADV 37)
            elif self.section == "EVANGELIUM" and k in ("text", "italic", "verse", "rubric_c"):
                self.parse_reading("EVANGELIUM")
            elif k == "rubric" and self.section == "HYMNUS" and is_stanza_no(L):
                self.parse_text_block()
            elif k == "text" and t.startswith("Deus, in adiutórium") and not self.section:
                self.i += 1   # opening printed without its ℣ sign (source quirk, e.g. PA 277)
                self.emit("versicle", [L], "OPENING", {"pairs": [["V", markup(L)]], "nosign": True})
            elif k == "rubric_c" or (k == "rubric" and self.section in ("PSALMODIA", "CANTICUM EVANGELICUM")
                                     and PSALM_HEAD_RE.match(t)) or (k == "rubric" and PSALM_VEL_RE.match(t)):
                self.parse_psalm_or_meta()
            elif k == "verse" and self.section in ("PSALMODIA", "CANTICUM EVANGELICUM", "") and self.last_psalm:
                self.parse_psalm_body(self.last_psalm, continuing=True)
            elif k in ("V", "R"):
                self.parse_vr()
            elif self.section in ("CANTICUM EVANGELICUM", "ORATIO") and numbered(L):
                self.parse_numbered()
            elif k == "rubric" and self.inline_variant(L):
                self.parse_ant()     # "Pro virgine: Veni, sponsa Christi…": a variant antiphon printed without "Ant."
            elif k == "rubric" and self.is_inline_alt_ant(L):
                self.parse_alt_ant()
            elif k == "rubric":
                self.i += 1
                self.parse_rubric(L)
            elif k == "link":
                self.i += 1
                self.parse_link(L)
            elif (k == "text" and self.section == "CANTICUM EVANGELICUM" and self.cond.get("alt") == "Vel:"
                  and L.block_start and self.cur_ant is not None):
                self.parse_ant(bare=True)   # "Vel:" then an alternative antiphon without "Ant." (Saturday BVM)
            elif k in ("text", "italic", "verse"):
                self.parse_text_block()
            else:
                self.i += 1
                self.emit("unparsed", [L], data={"why": f"kind {k} in section {self.section!r}"})
        if self.h.code == "MIDDAY":
            self.infer_terce()
        self.split_variant_stanzas()
        return self.els

    def infer_terce(self):
        """Seasonal Hora media whose 'Ad Tertiam' sub-header is missing before Terce's short reading (LQP 1500):
        the closing elements between the psalmody and 'Ad Sextam' belong to Terce."""
        subs = [i for i, e in enumerate(self.els) if e.slot == "SUBHOUR"]
        last_ps = max((i for i, e in enumerate(self.els) if e.slot.startswith("PS")), default=None)
        if last_ps is None:
            return
        after = [i for i in subs if i > last_ps]
        if not after or self.els[after[0]].sub != "SEXT":
            return                          # 'Ad Tertiam' printed (or a layout without per-hour sections)
        for e in self.els[last_ps + 1:after[0]]:
            if e.slot in ("LB", "V", "ORATIO", "LECTIO BREVIS") and not e.sub:
                e.sub = "TERCE"

    def section_was_psalmody(self):
        return any(e.slot.startswith("PS") for e in self.els)

    # -- sub-variants (Commons, Office of the Dead)
    def inline_variant(self, L: Line) -> bool:
        """A red sub-variant label followed by black text on the same line: "Pro virgine: Veniénte Sponso…"."""
        r0 = L.runs[0]
        if not r0.red or not any(not r.red and r.text.strip() for r in L.runs[1:]):
            return False
        head = r0.text.strip()
        return bool(subvariant(head)) and head.endswith(":")

    def reopen_section(self):
        """An alternative ("Pro episcopo:", "Vel alia:", "Vel aliæ:") to an item whose section has already closed:
        reopen it, so that the alternative is parsed like the item (oratio, preces, short responsory, reading)."""
        last = next((e for e in reversed(self.els) if e.type not in ("rubric", "label", "marker", "link")), None)
        if last is None:
            return
        if last.type == "oratio":
            self.section = "ORATIO"
        elif last.type == "preces":
            self.section = "PRECES"
        elif last.type == "resp_breve":
            # "Pro una martyre:" + another short responsory (COM 156), or "Vel: Cf. Is 61, 10" + another short reading
            nxt = self.peek()
            self.section = "RESPONSORIUM BREVE" if nxt is not None and nxt.kind in ("R", "V") else "LECTIO BREVIS"
        elif last.type == "responsory":
            rd = next((e for e in reversed(self.els) if e.type == "reading"), None)
            if rd is not None:
                self.section = "LECTIO PRIOR" if rd.slot == "LECT1" else "LECTIO ALTERA"

    def split_variant_stanzas(self):
        """Parallel stanza variants inside a hymn ("Pro papa:" / "Pro episcopo:" / "Pro presbytero:", each replacing
        one stanza): the source prints the hymn's remaining common stanzas straight after the last variant, with no
        marker. Split them off that variant (at the line count of the previous variant) and give them the condition
        of the hymn fragment the variants interrupt."""
        def amen(e):
            return e.lines[-1].text.rstrip().endswith("Amen.")

        groups, cur = [], []
        for e in self.els:
            if e.type == "hymn":
                cur.append(e)
            elif e.type != "rubric" and cur:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        for g in groups:
            j = 0
            while j + 1 < len(g):
                j += 1
                e, prev = g[j], g[j - 1]
                if "for" not in e.cond or "for" not in prev.cond or amen(prev):
                    continue
                n = len(prev.lines)
                if len(e.lines) <= n or not e.lines[n].block_start:
                    continue
                k = j - 1
                while k >= 0 and "for" in g[k].cond and not amen(g[k]) and len(g[k].lines) == n:
                    k -= 1
                if k < 0 or amen(g[k]):
                    continue
                tail = Element("hymn", "HYMN", e.sub, {x: v for x, v in g[k].cond.items() if x == "for"},
                               hymn_data(e.lines[n:]), e.lines[n:])
                e.lines = e.lines[:n]
                e.data = hymn_data(e.lines)
                self.els.insert(self.els.index(e) + 1, tail)
                g.insert(j + 1, tail)        # the next hymn is compared with this (complete) tail, not the variant
                j += 1

    # -- antiphons
    def parse_ant(self, bare: bool = False):
        """bare: an antiphon printed as plain text without its red label — an alternative after a "Vel:" rubric
        (COM), or a Year A/B/C Gospel antiphon after "Anno X" (ADV 37)."""
        first = self.L[self.i]
        self.i += 1
        cont = self.take_while(lambda L: L.kind in ("text", "italic") and xclass(L) == 0 and not L.block_start)
        # page-break continuation: next page starts flush-left with lowercase or punctuation-led text (also after
        # a multi-line antiphon, ADV 1705), or (ADV 1748) with a capital when the antiphon so far stops mid-sentence
        nxt = self.peek()
        last = cont[-1] if cont else first
        if nxt and nxt.page_top and nxt.kind == "text" and xclass(nxt) == 0 and (
                nxt.text[:1].islower() or not re.search(r"[.!?:;»)]\s*†?$", last.text)):
            self.i += 1
            cont = cont + [nxt] + self.take_while(
                lambda L: L.kind in ("text", "italic") and xclass(L) == 0 and not L.block_start)
        if self.h.pdf in SANCTIS_SOURCES:
            # an unfinished antiphon continues across a block or page break (SP 476 "turbam multam", SQ 55)
            while True:
                nxt, last = self.peek(), (cont[-1] if cont else first)
                if not (nxt and nxt.kind == "text" and xclass(nxt) == 0 and (
                        (nxt.text[:1].islower() and not re.search(r"[.!?]$", last.text))
                        or (self.h.pdf == "COM" and nxt.page_top and not ANNO_RE.match(nxt.text)
                            and nxt.text != "Pater noster."))):   # "Iesu." (COM 1275), "At ille…" (COM 440)
                    break
                cont.append(nxt)
                self.i += 1
        lines = [first] + cont
        red = "" if bare else first.runs[0].text.strip()
        m = re.match(r"Ant\.\s*(\d)?\s*(.*)$", red)
        num = m.group(1) if m else None
        prefix = (m.group(2) if m else "").strip()
        text = norm_space(" ".join([markup(first, skip_first=not bare)] + [markup(L) for L in cont]))
        data = {"num": num, "text": text}
        if not m and red:
            data["lead"] = red            # inline sub-variant "Pro virgine: …" printed without "Ant."
        if bare:
            data["bare"] = True
        vcond = {}
        sv = subvariant(prefix or red) if (prefix or red).endswith(":") else None
        if sv:
            vcond["for"] = sv             # "Ant. pro virgine et martyre: …", "Pro pluribus: …"
        m2 = re.search(r"\s*<r>\s*†\s*</r>$", text)
        if m2:
            data["text"] = text = text[:m2.start()].rstrip()
            data["dagger"] = True
        if prefix:
            data["prefix"] = prefix
        prev = self.els[-1] if self.els else None
        if prev is not None and prev.type == "rubric" and prev.source_text.startswith("Loco responsorii"):
            # Triduum / Easter Octave: "Loco responsorii dicitur: Ant. Christus factus est / Hæc dies" — the antiphon
            # takes the short responsory's place (LQP 1129-1370)
            self.emit("ant", lines, "RB", data)
            return
        # sub-variant antiphons may share a text ("Pro religioso: Vos qui…" / "Pro religiosa: Vos qui…")
        seen_key = (self.section, self.sub, text) + (((prefix or red).lower(),) if vcond else ())
        prior = self.ants_seen.get(seen_key)
        repeat = prior is not None and (num is None or num == prior.data["num"])
        if self.section == "CANTICUM EVANGELICUM":
            slot = "GOSPEL_ANT"
        elif self.h.code == "INV":
            slot = "INV_ANT"
        elif self.section == "HYMNUS" and self.sub:
            slot = "ANT"          # seasonal Hora media: per-hour antiphon after the hymn
        elif self.section in ("PSALMODIA",) or self.h.code in ("MIDDAY",):
            slot = f"ANT{num}" if num else "ANT"
        elif num and self.section == "HYMNUS":
            slot = f"ANT{num}"    # numbered psalmody antiphon whose PSALMODIA label is not printed (LQP 2286)
        else:
            slot = "ANT"
        if repeat:
            data["repeat"] = True
            e = self.emit("ant", lines, prior.slot + "_R", data, keep_cond=True)
            e.cond = dict(prior.cond)
            if bare:
                self.cond.pop("alt", None)     # the "Vel:" before a repeated bare antiphon is used up here
        else:
            self.cond.update(vcond)
            e = self.emit("ant", lines, slot, data)
            self.cur_ant = e
            self.ants_seen[seen_key] = e

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

    def is_inline_alt_ant(self, L: Line) -> bool:
        """Red 'Vel:' + black antiphon text right after an antiphon (SP 100: 'Vel: Grátias tibi ago…').
        Enabled for the Sanctis volumes only; LQP (39×) and PA (1×) print the same pattern."""
        return (self.h.pdf in SANCTIS_SOURCES and len(L.runs) > 1 and L.runs[0].text.strip().lower() == "vel:"
                and not L.runs[1].red and bool(self.els) and self.els[-1].type == "ant")

    def parse_alt_ant(self):
        first = self.L[self.i]
        self.i += 1
        cont = self.take_while(lambda L: L.kind in ("text", "italic") and xclass(L) == 0 and not L.block_start)
        lines = [first] + cont
        text = norm_space(" ".join([markup(first, skip_first=True)] + [markup(L) for L in cont]))
        data = {"num": None, "text": text, "lead": first.runs[0].text.strip()}
        prev = self.els[-1]
        prior = self.ants_seen.get((self.section, self.sub, text))
        if prior is not None:
            data["repeat"] = True
            e = self.emit("ant", lines, prior.slot + "_R", data, keep_cond=True)
            e.cond = dict(prior.cond)
            return
        self.cond = {**self.cond, "alt": data["lead"]}
        if prev.cond.get("for"):
            self.cond["for"] = prev.cond["for"]   # "vel: …" after "Pro religioso: …" (COM 1540): same sub-variant
        e = self.emit("ant", lines, prev.slot[:-2] if prev.slot.endswith("_R") else prev.slot, data)
        self.ants_seen[(self.section, self.sub, text)] = e

    # -- psalms, canticles, and centred meta lines
    def parse_psalm_or_meta(self):
        L = self.L[self.i]
        t = L.text
        head = []
        nxt = self.peek(1)
        # heading wrapped after the comma: "Psalmus 68 (69)," / "2-22. 30-37" (ADV 1685, LQP 595)
        wrapped = t.endswith(",") and nxt is not None and nxt.kind == "rubric_c" and bool(
            PSALM_HEAD_RE.match(f"{t} {nxt.text}"))
        is_psalm = bool(PSALM_HEAD_RE.match(t) or PSALM_VEL_RE.match(t)) or wrapped or CANT_HEAD_RE.match(t) or (
            ROMAN_RE.match(t)) or (
            self.section == "CANTICUM EVANGELICUM" and re.match(r"^Lc \d", t)) or (
            self.section in VIGIL_READINGS and re.match(r"^Psalmi \d", t))
        if not is_psalm:
            # centred red line outside psalmody: reading refs/titles are handled in parse_text_block;
            # here it's a free-standing rubric (e.g. a title inside a reading section)
            self.i += 1
            self.emit("rubric", [L], data={"text": markup(L), "centered": True}, keep_cond=True)
            return
        head = []
        while self.i < len(self.L):
            X = self.L[self.i]
            if (X.kind == "rubric_c" and X.text != "Oratio") or (X is L and PSALM_VEL_RE.match(t)):
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
            mv = PSALM_VEL_RE.match(heads[0])
            if mv:
                data["alt_psalm"] = mv.group(2)       # "Psalmus 121 (122), vel 128 (129)" (COM 1684): either psalm
            m = PSALM_HEAD_RE.match(mv.group(1) if mv else heads[0])
            if wrapped:
                m = PSALM_HEAD_RE.match(f"{heads[0]} {heads[1]}")
            if m:
                vul, va, heb, ha, rng = m.groups()
                if heb:   # "Psalmus 9 A (9)", "Psalmus 18 B (19 B)", "Psalmus 114 (116 A)"
                    hebr = heb + (ha or "")
                else:     # same number in both systems: "Psalmus 6", "Psalmus 149"
                    hebr = vul + (va or "")
                data["psalm"] = {"vulg": vul + (va or ""), "hebr": hebr, "range": rng or ""}
                rest = heads[2:] if wrapped else heads[1:]
            elif CANT_HEAD_RE.match(heads[0]):
                data["canticle"] = True
                arg = CANT_HEAD_RE.match(heads[0]).group(1) or ""
                if arg and not ROMAN_RE.match(arg):     # "Canticum Eph 1, 3-10": reference on the same line
                    data["ref"] = arg
                    rest = heads[1:]
                else:                                   # "Canticum" / "Canticum I", reference on the next line
                    data["ref"] = heads[1] if len(heads) > 1 else ""
                    rest = heads[2:]
            elif heads[0].startswith("Psalmi "):
                # portions of several psalms sung as one chant: "Psalmi 41 (42), 2-3. 5 bcd; 42 (43), 3-4" (LQP 1195)
                data["canticle"] = True
                data["ref"] = heads[0]
                rest = heads[1:]
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
            elif (L.kind in ("R", "rubric") and re.match(r"^\(?\s*℟\. Allelúia", L.text)) or (
                    L.kind == "R" and e.data.get("canticle") and not e.data.get("gospel")):
                # canticle refrain: "℟. Allelúia" (Rev 19), "℟. Laudáte Dóminum, omnes gentes." (1 Tim 3, SPA 1012)
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
        if self.section == "LECTIO BREVIS" and self.h.code in ("LAUDS", "VESPERS", "V1", "V2") and pairs \
                and pairs[0][0] == "R":
            self.section = "RESPONSORIUM BREVE"     # label missing in the source (SPA 414, 1537): ℟ … * after LB
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
        if t.startswith("Vel:") and any(not r.red and r.text.strip() for r in L.runs[1:]):
            # inline alternative "Vel: Festivitátem … Dómino," whose text wraps onto a black line ("allelúia.", COM 864)
            lines += self.take_while(lambda X: X.kind == "text" and xclass(X) == 0 and not X.block_start)
        text = norm_space(" ".join(markup(X) for X in lines))
        plain = norm_space(" ".join(X.text for X in lines))
        last = self.last_content()
        nxt = self.peek()
        if self.h.pdf in SANCTIS_SOURCES and last is not None and last.type == "oratio" and plain.endswith(":") \
                and nxt is not None and nxt.kind == "text" and xclass(nxt) == 1 and not subvariant(plain):
            # another oratio follows: "vel:", "Vel, in sollemnitate dominica occurrenti:" (SPA 628, 691), "Vel, si
            # celebretur dominica:" (SADV 72), "Extra ipsam Basilicam Lateranensem:" (SPA 1821). PA/ADV print the
            # pattern twice each (Corpus Christi Compline) — left to their workstreams.
            self.section = "ORATIO"
            self.cond["alt"] = plain
        elif ALT_RE.match(plain):
            self.cond["alt"] = plain
            # an alternative printed without its label: a short reading after the short responsory ("Vel (Ap 12, 1):"),
            # or another reading after a responsory ("Vel alia:", "aut de die 16 iulii:")
            prev = self.last_content()
            m = re.match(r"^Vel \((.+)\):$", plain) or re.match(   # COM form: "Vel: Cf. Is 61, 10"
                r"^Vel: ((?:Cf\. )?[1-4]?\s?[A-Z][a-z]+ \d+, [\dab.\- ]+)$", plain)
            if m and prev is not None and prev.slot in ("RB", "LB"):
                self.section, self.alt_ref = "LECTIO BREVIS", m.group(1)
            elif prev is not None and prev.slot in ("RESP1", "RESP2") and not self.section:
                self.section = "LECTIO PRIOR" if prev.slot == "RESP1" else "LECTIO ALTERA"
        elif re.match(r"^I+\. Quando Officium lectionis", plain):
            self.cond["variant"] = "night" if plain.startswith("I.") else "day"
        elif "non dicitur Glória Patri" in plain or "non dicitur Gloria Patri" in plain:
            if self.last_psalm is not None:
                self.last_psalm.data["no_gloria"] = True
        elif plain.startswith("Deinde legitur Evangelium"):
            self.section = "EVANGELIUM"     # Christmas vigil: canticles, then the Gospel (ADV 8418)
        sv = subvariant(plain)
        if sv:
            self.cond["for"] = sv
            if plain.startswith("Alia,"):
                self.cond["alt"] = plain
        if plain.startswith("Ubi vigilia protrahitur"):
            self.cond["alt"] = plain             # reading for a prolonged vigil (Communia, Martyrs)
        if (sv or ALT_REOPEN_RE.match(plain)) and not self.section:
            self.reopen_section()
        self.emit("rubric", lines, "", {"text": text}, keep_cond=True)

    def parse_link(self, L: Line):
        more = self.take_while(lambda X: X.kind in ("rubric", "rubric_c") and X.block == L.block and not X.block_start)
        if L.text.startswith("Antiphonæ finales"):   # "… Hodie convenienter dicitur ant. Ave, / Regína cælórum." (SPA 1145)
            more += self.take_while(lambda X: X.kind == "text" and X.block == L.block and not X.block_start)
        t = norm_space(" ".join([L.text] + [X.text for X in more]))
        if more:
            slot = "SUBST" if "Invitatori" in t else "MARIAN" if t.startswith("Antiphonæ finales") else "LINK"
            self.emit("link", [L] + more, slot, {"text": t, "target": L.link}, keep_cond=True)
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
    def missing_label(self) -> str:
        """Recover a section whose red label the source forgot (reported in TODO.md §3):
        a hymn right after the opening (SPA 259, 2067, 2357), the second reading of the Office of Readings
        recognised by its centred source citation (SPA 1314)."""
        content = [e for e in self.els if e.type not in ("marker", "rubric")]
        if self.h.code in ("OR", "LAUDS", "VESPERS", "V1", "V2") and content and \
                all(e.slot == "OPENING" for e in content):
            return "HYMNUS"
        nxt = [self.peek(j) for j in (1, 2)]
        if self.h.code == "OR" and not any(e.slot == "LECT2" for e in self.els) and any(
                X is not None and X.kind == "rubric_c" and X.text.startswith("(") for X in nxt):
            return "LECTIO ALTERA"
        return ""

    def parse_text_block(self):
        if not self.section or (self.section == "HYMNUS" and self.els and self.els[-1].type == "rubric"):
            self.section = self.missing_label() or self.section
        sec = self.section
        if sec == "HYMNUS":
            lines = self.take_while(lambda X: X.kind in ("text", "italic") or (X.kind == "rubric" and is_stanza_no(X)))
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
            lines = self.take_while(lambda X: X.kind in ("text", "italic", "rubric") and not X.text.startswith("Oratio"))
            self.emit("te_deum", lines, "TE_DEUM", {"lines": [[X.kind, markup(X)] for X in lines]})
            self.section = ""
            return
        if sec in ("LECTIO PRIOR", "LECTIO ALTERA", "LECTIO") or sec in VIGIL_READINGS:
            self.parse_reading(sec)
            return
        if sec.startswith("ANTIPHONA FINALIS"):
            # Marian antiphon printed in full (Eastertide Compline: Regína cæli, GILH 92), not linked to the Ordinary
            lines = self.take_while(lambda X: X.kind in ("text", "italic"))
            self.emit("text", lines, "MARIAN", {"lines": [[xclass(X), markup(X)] for X in lines]})
            self.section = ""
            return
        if self.dash_ahead():
            # preces without their PRECES label (LQP 2522) or resumed after an interruption ("Vel aliæ:", PA 6277)
            self.parse_preces()
            return
        lines = self.take_while(lambda X: X.kind in ("text", "italic") and X.text != "Pater noster."
                                and X.text.upper() not in LABELS)
        if not lines and self.L[self.i].text.upper() in LABELS:
            # a label set in black roman type ("Responsorium breve", SPA 1540): treat it as the label
            L = self.L[self.i]
            self.i += 1
            self.section = L.text.upper()
            self.emit("label", [L], self.section, {"label": self.section, "ref": ""}, keep_cond=True)
            return
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
            if X.kind in ("V", "R", "ant", "dash") or X.text.startswith("Hymnus Te Deum"):
                break
            if sec == "EVANGELIUM" and X.kind == "rubric" and lines:
                break                         # "Vel forma breviore:" starts the alternative (shorter) Gospel
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
        slot = VIGIL_READINGS.get(sec) or {"LECTIO PRIOR": "LECT1", "EVANGELIUM": "GOSPEL"}.get(sec, "LECT2")
        self.emit("reading", lines, slot, {"intro": intro, "meta": meta, "lines": body})

    def parse_preces(self):
        intro, response, petitions, lines = [], "", [], []
        response_alt = ""
        first_half: list[str] = []
        alt = False
        while self.i < len(self.L):
            X = self.L[self.i]
            if X.kind == "text" and X.text == "Pater noster.":
                break
            if X.kind == "italic" and not response:
                response = markup(X)
            elif (X.kind == "rubric" and response and not response_alt and not petitions and not first_half
                  and X.text.startswith("Vel:")):
                response_alt = markup(X)         # alternative response, e.g. "Vel: Plenam grátia intuére…" (SP 287)
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
        if response_alt:
            data["response_alt"] = response_alt
        if first_half:
            data["tail"] = norm_space(" ".join(first_half))
        self.emit("preces", lines, "PRECES", data)
        self.section = ""


def parse_hour(hour: Hour) -> Hour:
    hour.elements = HourParser(hour).parse()
    return hour

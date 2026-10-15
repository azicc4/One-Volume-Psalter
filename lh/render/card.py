"""The Ordinary card: the fixed parts of the hours on one card that lives in the book (TODO B-14).

The simulation (reports/simulation.md) found the Ordinary's fixed parts — on four spreads of the book — to be the
largest single cost in turning: about ten look-ups a day. The card carries them, so that each hour is said from its
heading in the Proper (or the Psalter) with the card in hand. One sheet, 11 × 8.5 in landscape, printed on both
sides, two panels a side (folded along the faint line between them, it fits inside the book):

  front, left    Invitatory (opening versicle, Psalm 95, alternatives by page); opening of the other hours
  front, right   Benedictus, Pater noster, prayer endings, dismissal of Lauds and Vespers
  back, left     Magnificat, dismissal of the other hours, Nunc dimittis, blessing at Compline
  back, right    Te Deum, antiphons of the Blessed Virgin Mary

Texts come from the database (and the Ordinary supplement), rendered by the book's own renderers; page numbers of
the book come from its last build (build/latex/book.aux). Output: book/out/card.pdf (2 pages, front and back).
"""
from __future__ import annotations

import re

from lh.config import BOOK, BUILD, VARIANTS
from lh.render import latex as L
from lh.model.attribute import content
from lh.render.common import cant_key, load_supplement, sup_pairs
from lh.render.latex import esc, label, tex

AUX = BUILD / "latex" / "book.aux"
NEWLABEL = re.compile(r"\\newlabel\{([^}]*)\}\{\{[^}]*\}\{([^}]*)\}")
GLORIA = (r"\psl{}{Glória Patri et Fílio \mediant{}}\psk{et Spirítui Sancto.}"
          r"\psc{Sicut erat in princípio et nunc et semper \mediant{}}\psk{et in sǽcula sæculórum. Amen.}")


def book_pages(aux=AUX) -> dict[str, str]:
    """LaTeX label → printed page number in the last full build of the book."""
    if not aux.exists():
        return {}
    return dict(NEWLABEL.findall(aux.read_text(encoding="utf-8", errors="replace")))


class Card:
    def __init__(self, book, aux=AUX):
        self.b = book
        self.s = load_supplement()
        self.pages = book_pages(aux)

    def pg(self, lab: str) -> str:
        p = self.pages.get(lab)
        return f"p.\\,{p}" if p else ""

    # ------------------------------------------------------------------ texts
    def instance_items(self, chap: str, hour: str | None = None) -> list:
        insts = [h for h in self.b.chapter_instances(chap) if hour is None or h["hour"] == hour]
        return list(self.b.db.occ(insts[0]["id"])) if insts else []

    def rubric_or_text(self, occs) -> list[str]:
        out = []
        for o in occs:
            if o["type"] in ("label", "marker") or not o["object_id"]:
                continue
            ob = self.b.objs[o["object_id"]]
            if o["type"] == "rubric":
                out.append(r"\rubr{" + tex(ob.payload.get("text", ""), marks=False) + "}")
            elif ob.type in L.RENDER:
                out.append(L.render(ob.type, ob.payload))
        return out

    def invitatory_psalms(self):
        insts = self.b.chapter_instances("INVITATORY")
        psalms = []
        for o in content(self.b.db.occ(insts[0]["id"])) if insts else []:
            ob = self.b.objs[o["object_id"]]
            if ob.type == "psalm" and ob.id not in [p.id for p in psalms]:
                psalms.append(ob)
        return psalms

    def gospel(self, ref: str):
        vs = [o for o in self.b.objs.values() if o.type == "canticle" and o.payload.get("gospel")
              and cant_key(o.payload["ref"]) == cant_key(ref)]
        return max(vs, key=lambda o: o.n_occ) if vs else None

    def canticle(self, title: str, ref: str, when: str) -> list[str]:
        o = self.gospel(ref)
        if not o:
            return []
        return [r"\cardhead{" + title + "}{" + esc(o.payload["ref"]) + " · " + when + "}",
                L.canticle_lines(o.payload["lines"]), GLORIA]

    def dismissal(self, hour: str) -> list[str]:
        """The dismissal versicles of an hour, with short English rubrics in place of the Ordinary's long ones."""
        vrs = [self.b.objs[o["object_id"]] for o in self.instance_items("DISMISSAL", hour)
               if o["object_id"] and o["type"] not in ("rubric", "label", "marker")]
        if hour in ("LAUDS", "VESPERS") and len(vrs) >= 3:
            return [r"\rubr{If a priest or deacon presides:} " + L.render(vrs[0].type, vrs[0].payload),
                    r"\par\rubr{and, to dismiss the people:} " + L.render(vrs[1].type, vrs[1].payload),
                    r"\par\rubr{Otherwise, and when said alone:} " + L.render(vrs[2].type, vrs[2].payload)]
        return [L.render(o.type, o.payload) for o in vrs]

    # ------------------------------------------------------------------ the four faces
    def faces(self) -> list[tuple[str, list[str]]]:
        s, b = self.s, self.b
        inv = self.invitatory_psalms()
        f1 = [r"\cardhead{Ad Invitatorium}{before the first hour of the day}", sup_pairs(s["invitatory_opening"]),
              r"\par\rubr{The antiphon of the day (in the Propers) is said and repeated; then the psalm, the antiphon "
              r"repeated after each strophe.}"]
        if inv:
            p = inv[0].payload
            # the psalm ends with its own Glória Patri
            f1 += [r"\cardhead{Psalm " + esc(p["psalm"]) + " (" + esc(p["vulg"]) + ")}{" + tex(p.get("title", ""), marks=False) + "}",
                   L.canticle_lines(p["lines"])]
            alts = [f"Ps {esc(o.payload['psalm'])} {self.pg(label(o.id))}" for o in inv[1:]]
            if alts:
                f1.append(r"\par\rubr{In place of Psalm 95: " + "; ".join(alts) + ".}")
        f1 += [r"\cardhead{Ad omnes Horas}{opening, except when the Invitatory precedes}", sup_pairs(s["opening"]),
               r"\par " + tex(s["gloria_short"]) + r" \rubr{Allelúia (omitted in Lent).}"]
        f2 = self.canticle("Benedictus", "Lc 1, 68-79", "at Lauds, with the antiphon of the day")
        f2 += [r"\cardhead{Pater noster}{Lauds and Vespers, after the intercessions}", tex(s["pater_noster"]),
               r"\cardhead{Prayer endings}{}"]
        f2 += [r"\par{\footnotesize\rubric{" + esc(k) + r"}\enspace " + tex(v) + "}" for k, v in s["conclusions"].items()]
        f2 += [r"\cardhead{Dismissal}{Lauds and Vespers}"] + self.dismissal("LAUDS")
        f3 = self.canticle("Magnificat", "Lc 1, 46-55", "at Vespers, with the antiphon of the day")
        f3 += [r"\cardhead{Dismissal}{Office of Readings, Daytime Prayer}"] + self.dismissal("MIDDAY")
        f3 += self.canticle("Nunc dimittis", "Lc 2, 29-32", "at Compline, with its antiphon")
        f3 += [r"\cardhead{Benedictio}{at the end of Compline, even alone}"] + self.dismissal("COMPLINE")
        tedeum = max((o for o in b.objs.values() if o.type == "te_deum"), key=lambda o: o.n_occ, default=None)
        f4 = []
        if tedeum:
            f4 += [r"\cardhead{Te Deum}{Office of Readings: Sundays outside Lent, solemnities, feasts, octaves}",
                   r"{\small " + L.te_deum(tedeum.payload) + "}"]
        f4 += [r"\cardhead{Antiphonæ finales B.\,M.\,V.}{after Compline; in Eastertide Regína cæli}"]
        marian = [o for o in self.instance_items("MARIAN") if o["type"] == "text" and o["object_id"]]
        rc = sorted((o for o in b.objs.values() if o.id.startswith("txt.regina-caeli")), key=lambda o: -o.n_occ)
        for ob in [b.objs[o["object_id"]] for o in marian] + rc[:1]:
            f4.append(r"\cardant{" + L.render(ob.type, ob.payload) + "}")
        return [("Front · Invitatory, opening of the hours", f1), ("Front · Lauds, Pater noster, dismissal", f2),
                ("Back · Vespers and Compline", f3), ("Back · Te Deum, Marian antiphons", f4)]

    def body(self) -> str:
        """Four panels in two columns: panels 1–2 the front, 3–4 the back."""
        out = []
        for i, (name, parts) in enumerate(self.faces()):
            out.append(r"\cardface{" + name + "}")
            out += parts
            out.append(r"\newpage" if i % 2 == 0 else r"\clearpage")       # next column / next side
        return "\n".join(out)


def write_card(book, variant: str = "main") -> str:
    """book/generated/<card>_body.tex for a variant of the book (its own page numbers: build/latex/<file>.aux)."""
    v = VARIANTS[variant]
    out = BOOK / "generated" / f"{v['card']}_body.tex"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(Card(book, BUILD / "latex" / f"{v['file']}.aux").body(), encoding="utf-8")
    return str(out)

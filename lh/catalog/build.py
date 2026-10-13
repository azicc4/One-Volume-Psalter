"""L7: static, searchable reference catalog of the database → reference/index.html + reference/data.js.

Open reference/index.html in a browser (no server needed). Search objects by text (accent-insensitive), see each
object's full text, verification status and every place it is printed (day, hour, slot, source PDF page — the page
link opens the original PDF at that page), or browse any hour reassembled from its objects.
"""
from __future__ import annotations

import json
import re
import sqlite3

from lh.config import DB_PATH, PDFS, ROOT
from lh.model.canon import fold, paragraphs, plain
from lh.model.days import HOUR_NAMES

OUT = ROOT / "reference"


def html_markup(s: str) -> str:
    s = (s or "").replace("&", "&amp;").replace("<i>", "\x01").replace("</i>", "\x02").replace("<r>", "\x03") \
        .replace("</r>", "\x04").replace("<v>", "\x05").replace("</v>", "\x06").replace("<", "&lt;").replace(">", "&gt;")
    return s.replace("\x01", "<i>").replace("\x02", "</i>").replace("\x03", '<span class="r">').replace("\x04", "</span>") \
        .replace("\x05", '<sup class="r">').replace("\x06", "</sup>")


def obj_html(otype: str, p: dict) -> str:
    h = html_markup
    if otype == "hymn":
        return "".join("<p>" + "<br>".join(h(l) for l in st) + "</p>" for st in p["stanzas"])
    if otype in ("psalm", "canticle"):
        out = []
        for l in p["lines"]:
            v = f'<span class="vn">{h(l["v"])}</span>' if l.get("v") else '<span class="vn"></span>'
            cls = "c" if l["x"] >= 2 else "l"
            out.append(f'<div class="{cls}">{v}{h(l["t"])}</div>')
        return "".join(out)
    if otype in ("versicle", "responsory", "resp_breve"):
        return "".join(f'<p><span class="r">{"℣" if k == "V" else "℟"}.</span> {h(v)}</p>' for k, v in p["pairs"])
    if otype == "reading":
        parts = [f"<p><small>{h(x)}</small></p>" for x in p.get("intro", []) + p.get("meta", [])]
        return "".join(parts) + "".join(f"<p>{h(x)}</p>" for x in paragraphs(p.get("lines", [])))
    if otype == "preces":
        out = [f"<p>{h(p.get('intro', ''))}</p>", f"<p><i>{h(p.get('response', ''))}</i></p>"]
        out += [f"<p>{h(x['a'])}<br>— {h(x['b'])}</p>" for x in p.get("petitions", [])]
        return "".join(out)
    if otype == "te_deum":
        return "".join(f"<div>{h(x)}</div>" for _, x in p["lines"])
    if otype == "ant":
        return f"<p>{h(p['text'])}</p>"
    if "lines" in p:
        return "".join(f"<p>{h(x)}</p>" for x in paragraphs(p["lines"]))
    return f"<p>{h(p.get('text', ''))}</p>"


def build_catalog(db=DB_PATH) -> str:
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    pdf_files = {k: (ROOT / v).as_uri() for k, v in PDFS.items()}
    flags = {}
    for subj, status in con.execute("SELECT subject, status FROM check_result WHERE check_name='variants'"):
        for oid in subj.split(" ~ "):
            flags[oid] = "near-duplicate of another object (review)"
    objects = {}
    for r in con.execute("SELECT id, type, payload, n_occ, plain FROM object WHERE type NOT IN ('link','rubric','unparsed')"):
        p = json.loads(r["payload"])
        objects[r["id"]] = {"t": r["type"], "n": r["n_occ"], "h": obj_html(r["type"], p),
                            "s": fold(r["plain"])[:4000], "x": plain(r["plain"])[:140], "f": flags.get(r["id"], "")}
    days = {r["key"]: {"title": r["title"], "season": r["season"], "pw": r["psalter_week"]} for r in con.execute("SELECT * FROM day")}
    hours = []
    occ_by_obj: dict[str, list] = {}
    q = """SELECT o.hour_id, o.seq, o.slot, o.sub, o.cond, o.object_id, o.page, o.type, h.day_key, h.hour, h.source, h.copy
           FROM occurrence o JOIN hour_instance h ON h.id=o.hour_id ORDER BY o.hour_id, o.seq"""
    cur_h, items = None, []
    hmeta = {}
    for r in con.execute(q):
        if r["hour_id"] != cur_h:
            if cur_h is not None:
                hours.append({**hmeta, "items": items})
            cur_h, items = r["hour_id"], []
            hmeta = {"id": r["hour_id"], "day": r["day_key"], "hour": r["hour"], "src": r["source"], "copy": r["copy"]}
        if r["object_id"] and r["object_id"] in objects:
            items.append([r["slot"] + (f"@{r['sub']}" if r["sub"] else ""), r["object_id"], r["page"],
                          json.loads(r["cond"]) if r["cond"] else None])
            occ_by_obj.setdefault(r["object_id"], []).append([r["hour_id"], r["slot"] + (f"@{r['sub']}" if r["sub"] else ""),
                                                              r["source"], r["page"]])
    if cur_h is not None:
        hours.append({**hmeta, "items": items})
    for oid, occ in occ_by_obj.items():
        objects[oid]["o"] = occ
    data = {"objects": objects, "days": days, "hours": hours, "pdf": pdf_files, "hourNames": HOUR_NAMES}
    OUT.mkdir(exist_ok=True)
    (OUT / "data.js").write_text("window.LH=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";",
                                 encoding="utf-8")
    (OUT / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return str(OUT / "index.html")


INDEX_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Liturgia Horarum Reference</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1b18;--mut:#6b655c;--red:#a8161b;--line:#e4dfd6;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#171513;--fg:#ece7df;--mut:#a39b8f;--red:#ff7b72;--line:#38332d;--card:#211e1b}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 Georgia,'EB Garamond',serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;z-index:2}
h1{font-size:17px;margin:0 0 6px;font-variant:small-caps;color:var(--red)}
input,select{font:inherit;padding:5px 8px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:4px}
#q{width:min(520px,60vw)} nav button{font:inherit;background:none;border:0;color:var(--red);cursor:pointer;margin-right:12px}
main{display:grid;grid-template-columns:minmax(260px,420px) 1fr;gap:0;min-height:80vh}
#list{border-right:1px solid var(--line);overflow:auto;max-height:calc(100vh - 90px)}
#detail{padding:14px 20px;overflow:auto;max-height:calc(100vh - 90px)}
.row{padding:7px 14px;border-bottom:1px solid var(--line);cursor:pointer}.row:hover{background:var(--card)}
.id{font:12px/1.3 ui-monospace,Consolas,monospace;color:var(--mut)} .t{font-size:12px;color:var(--red);font-variant:small-caps}
.r{color:var(--red)} .vn{display:inline-block;width:2.2em;color:var(--red);font-size:11px}
.c{padding-left:3.2em} .l{padding-left:0} table{border-collapse:collapse;font-size:13px;margin-top:8px}
td,th{border-bottom:1px solid var(--line);padding:3px 8px;text-align:left} a{color:var(--red)}
.flag{background:#f5d9a8;color:#3b2a00;padding:1px 6px;border-radius:3px;font-size:12px}
.slot{font-size:12px;color:var(--mut);font-variant:small-caps;margin-top:8px}
@media (max-width:760px){main{grid-template-columns:1fr}#list{max-height:40vh;border-right:0;border-bottom:1px solid var(--line)}}
</style></head><body>
<header><h1>Liturgia Horarum — reference catalog</h1>
<input id="q" placeholder="Search text or id (accents optional), e.g. ad te orabo mane"> <select id="ty"><option value="">all types</option></select>
<nav style="margin-top:6px"><button id="bDays">Browse days &amp; hours</button><span id="count" class="id"></span></nav></header>
<main><div id="list"></div><div id="detail"><p class="id">Select an object or an hour.</p></div></main>
<script src="data.js"></script>
<script>
const D=window.LH, O=D.objects, H=Object.fromEntries(D.hours.map(h=>[h.id,h]));
const fold=s=>s.normalize('NFKD').replace(/[̀-ͯ]/g,'').replace(/æ/g,'ae').replace(/œ/g,'oe').toLowerCase();
const types=[...new Set(Object.values(O).map(o=>o.t))].sort(); const ty=document.getElementById('ty');
types.forEach(t=>ty.add(new Option(t,t)));
const list=document.getElementById('list'), det=document.getElementById('detail');
function hourLabel(h){const d=D.days[h.day]||{};return `${d.title||h.day} — ${D.hourNames[h.hour]||h.hour}${h.copy?' '+h.copy:''}`}
function search(){const q=fold(document.getElementById('q').value.trim()), t=ty.value; const words=q.split(/\s+/).filter(Boolean);
 let res=Object.entries(O).filter(([id,o])=>(!t||o.t===t)&&words.every(w=>o.s.includes(w)||id.includes(w)));
 res.sort((a,b)=>b[1].n-a[1].n); document.getElementById('count').textContent=` ${res.length} objects`;
 list.innerHTML=res.slice(0,300).map(([id,o])=>`<div class="row" data-id="${id}"><div class="t">${o.t} · ×${o.n} ${o.f?'<span class=flag>review</span>':''}</div>${o.x}<div class="id">${id}</div></div>`).join('');}
function showObj(id){const o=O[id]; if(!o)return;
 const occ=(o.o||[]).map(([hid,slot,src,pg])=>{const h=H[hid];return `<tr><td><a href="#" data-h="${hid}">${hourLabel(h)}</a></td><td>${slot}</td><td><a href="${D.pdf[src]}#page=${pg}" target="_blank">${src} p.${pg}</a></td></tr>`}).join('');
 det.innerHTML=`<div class="t">${o.t}</div><div class="id">${id}</div>${o.f?`<p><span class=flag>${o.f}</span></p>`:''}<div>${o.h}</div>
 <h3 class="r" style="font-variant:small-caps;font-size:15px">Printed ${o.n} time(s)</h3><table><tr><th>Day — hour</th><th>Slot</th><th>Source page</th></tr>${occ}</table>`;}
function showHour(hid){const h=H[hid]; det.innerHTML=`<h2 class="r" style="font-size:17px">${hourLabel(h)}</h2>`+
 h.items.filter(([s])=>!s.endsWith('_R')).map(([slot,id,pg,cond])=>`<div class="slot">${slot}${cond?' · '+Object.values(cond).join(' '):''} · <a href="#" data-id="${id}">${id}</a> · <a href="${D.pdf[h.src]}#page=${pg}" target="_blank">p.${pg}</a></div>${O[id].h}`).join('');}
function browse(){const byDay={}; D.hours.forEach(h=>(byDay[h.day]=byDay[h.day]||[]).push(h));
 list.innerHTML=Object.keys(byDay).sort().map(k=>`<div class="row"><b>${(D.days[k]||{}).title||k}</b> <span class="id">${k}</span><br>${byDay[k].map(h=>`<a href="#" data-h="${h.id}">${D.hourNames[h.hour]||h.hour}${h.copy?' '+h.copy:''}</a>`).join(' · ')}</div>`).join('');}
document.getElementById('q').addEventListener('input',search); ty.addEventListener('change',search);
document.getElementById('bDays').onclick=browse;
document.body.addEventListener('click',e=>{const a=e.target.closest('[data-id],[data-h]'); if(!a)return; if(a.tagName==='A')e.preventDefault();
 if(a.dataset.id)showObj(a.dataset.id); else showHour(+a.dataset.h);});
search();
</script></body></html>
"""

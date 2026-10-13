-- One-Volume Psalter database. Rebuilt deterministically by `python -m lh build`.
-- Every printed thing in the sources is an OCCURRENCE (with page provenance) of a canonical OBJECT.

CREATE TABLE source (
    key TEXT PRIMARY KEY, pdf TEXT, sha256 TEXT, pages INTEGER,
    p0 INTEGER, p1 INTEGER             -- page scope parsed (NULL = whole PDF), e.g. ADV:4-1198
);

CREATE TABLE source_line (             -- lines outside any hour: headings, day preambles (rank, bio), front matter
    source TEXT, l1_first INTEGER, l1_last INTEGER, page INTEGER,
    role TEXT,                         -- heading | day_extra | front
    section TEXT, day_title TEXT, text TEXT
);

CREATE TABLE day (                     -- a liturgical day (or a proper/common "day")
    key TEXT PRIMARY KEY,              -- OT.05.SUN, SOL.TRINITY, …
    season TEXT, week INTEGER, weekday TEXT, psalter_week INTEGER,
    title TEXT, rank TEXT, precedence INTEGER,
    short TEXT                         -- short name for margin notes: "Trinity", "26 Dec", "Easter Sun"
);

CREATE TABLE hour_refs (               -- what a reader needs ribbons for, per hour (drives page refs at hour heads)
    hour_id INTEGER PRIMARY KEY REFERENCES hour_instance(id),
    day_key TEXT, hour TEXT,
    ordinary_anchor TEXT,              -- label of the hour in the Ordinary (ord:lauds …)
    psalm_units TEXT,                  -- JSON {"PS1": object_id, …}  (psalms and canticles, ≤3; INV: the invitatory psalm)
    readings TEXT                      -- JSON {"LECT1": id, "RESP1": id, "LECT2": id, "RESP2": id}  (Office of Readings)
);

CREATE TABLE hour_instance (           -- one printed hour in one source PDF
    id INTEGER PRIMARY KEY,
    source TEXT REFERENCES source(key),
    day_key TEXT REFERENCES day(key),
    hour TEXT,                         -- INV OR LAUDS MIDDAY VESPERS V1 V2 COMPLINE COMPLINE1
    section TEXT, day_title TEXT, subtitle TEXT,
    page_start INTEGER, page_end INTEGER,
    copy TEXT,                         -- duplicate-copy label (e.g. Advent start date); NULL if unique
    l1_first INTEGER, l1_last INTEGER  -- range of L1 line ids (build/l1/<source>.sqlite) covered by this hour
);
CREATE INDEX hour_day ON hour_instance(day_key, hour);

CREATE TABLE object (                  -- a canonical text, stored once
    id TEXT PRIMARY KEY,               -- readable + hash: ant.ad-te-orabo-domine.3f9a1c, ps.063.2-9.ab12
    type TEXT,                         -- hymn ant psalm canticle versicle reading responsory lectio_brevis resp_breve
                                       -- preces oratio te_deum prayer text rubric link ordinary_ref
    incipit TEXT,
    plain TEXT,                        -- plain text (search / catalog)
    payload TEXT,                      -- JSON with inline markup <r> <i> <v>
    hash TEXT,
    n_occ INTEGER,                     -- number of printed occurrences across all sources
    status TEXT,                       -- unverified | consensus | flagged
    home TEXT                          -- section of the new book where it is printed (set by attribution)
);
CREATE INDEX object_type ON object(type);

CREATE TABLE occurrence (              -- one printing of an object inside an hour (or a structural marker)
    id INTEGER PRIMARY KEY,
    hour_id INTEGER REFERENCES hour_instance(id),
    seq INTEGER,                       -- order within the hour
    type TEXT, slot TEXT, sub TEXT,    -- slot code (HYMN, ANT1, PS1, LB, GOSPEL_ANT, ORATIO…); sub = TERCE/SEXT/NONE
    cond TEXT,                         -- JSON: {"year":"A"}, {"variant":"night"}, {"alt":"Vel:"}
    object_id TEXT REFERENCES object(id),
    page INTEGER, page_end INTEGER,
    source_text TEXT,                  -- the joined source lines, for audit and round-trip
    extra TEXT                         -- JSON occurrence-level attributes (see lh/model/canon.py)
);
CREATE INDEX occ_obj ON occurrence(object_id);
CREATE INDEX occ_hour ON occurrence(hour_id);

CREATE TABLE link_target (             -- what a printed link (blue: "Vel alter", "Ad libitum dici potest hymnus Dies iræ.",
                                       -- "Memoria ad libitum Sanctæ Mariæ", "Conclusio Horæ…") points to in its source PDF
    occurrence_id INTEGER PRIMARY KEY REFERENCES occurrence(id),
    page INTEGER,                      -- target page (the PDF stores pages only, not positions)
    hour_id INTEGER REFERENCES hour_instance(id),     -- hour instance printed at the target
    target_occ INTEGER REFERENCES occurrence(id),     -- element at the target
    object_id TEXT REFERENCES object(id),             -- its object (e.g. the hymn named by an ad libitum link)
    how TEXT                           -- text: the link names the element (incipit / reading source) · page: first
                                       -- element on the target page (in an hour of the same kind when there is one)
);

CREATE TABLE psalm (                 -- the 150 psalms, Hebrew numbering primary
    num INTEGER PRIMARY KEY, vulgate TEXT, title TEXT, n_verses INTEGER
);

CREATE TABLE psalm_verse (             -- consensus text of every psalm verse line
    psalm INTEGER, seq INTEGER, verse TEXT, line INTEGER, x INTEGER, text TEXT,
    source TEXT,                       -- LH | NV (Nova Vulgata gap fill)
    n_copies INTEGER, n_agree INTEGER, used INTEGER,
    PRIMARY KEY (psalm, seq, line)
);

CREATE TABLE psalm_use (               -- where each psalm portion is prayed (drives the Psalter margin notes)
    occurrence_id INTEGER REFERENCES occurrence(id),
    psalm INTEGER, unit TEXT, verses TEXT, first TEXT, last TEXT, section TEXT,
    day_key TEXT, hour TEXT, slot TEXT, psalter_week INTEGER, weekday TEXT
);
CREATE INDEX use_psalm ON psalm_use(psalm);

CREATE TABLE check_result (            -- verification results (lh/verify)
    check_name TEXT, subject TEXT, status TEXT, detail TEXT
);

CREATE VIRTUAL TABLE object_fts USING fts5(
    id UNINDEXED, type UNINDEXED, plain, tokenize = 'unicode61 remove_diacritics 2'
);

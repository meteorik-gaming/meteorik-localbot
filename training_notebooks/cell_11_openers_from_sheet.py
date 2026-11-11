# CELL 11 -- opener seeds built from the reviewed reply sheet (any language). Run once, BEFORE cell 5, whenever the sheet changes.
# With this cell you do NOT upload any openers_*.txt: the sheet is the single source (openers_en_v3.txt has exactly the same 5,333 lines).
# LANG = "en": reads seeds/reply_sheet.csv    -> writes seeds/openers_en.txt
# LANG = "es": reads seeds/reply_sheet_es.csv -> writes seeds/openers_es.txt (gender-marker variants, below)
# Sheet columns: id,category,tags,message,reply_allowed,reply_restricted[,note]. Output is the cell 4b format cell 5 reads (category | tags | text).
#
# Gender markers: a player opener may contain {masc|fem} pairs ("estoy {cansado|cansada}"). Every such row is written
# THREE times, each with a context tag that cell 5 matches against the header's `player` line:
#     +male                 -> masculine forms     (header says "The user's gender is male.")
#     +female               -> feminine forms      (header says "The user's gender is female.")
#     !+male,!+female       -> masculine forms     (no gender line = unspecified; Bot then uses invariable words)
# Rows without markers are written once, untagged. Only the openers matter here: cell 12 turns the sheet's replies into
# training rows (it labels them and builds a matching header).
import csv, re, collections
LANG = globals().get("LANG", "en")
SHEET = BASE / "seeds" / ("reply_sheet_es.csv" if LANG == "es" else "reply_sheet.csv")
OUT = BASE / "seeds" / f"openers_{LANG}.txt"
MARKER = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}")


def resolve(text, gender):
    return MARKER.sub(lambda m: m.group(2) if gender == "female" else m.group(1), text)


rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig", newline="")))
lines, n_marked = [], 0
for r in rows:
    cat, tags, msg = r["category"].strip(), r["tags"].strip(), r["message"].strip()
    if not (cat and msg):
        continue
    if "\n" in msg:
        print("skipped", r["id"], "(newline in the opener)")
        continue
    base = [t.strip() for t in tags.split(",") if t.strip() and t.strip() != "-"]
    if MARKER.search(msg):
        n_marked += 1
        variants = [("male", ["+male"]), ("female", ["+female"]), ("unspecified", ["!+male", "!+female"])]
    else:
        variants = [("unspecified", [])]
    for g, extra in variants:
        lines.append(f"{cat} | {','.join(base + extra) or '-'} | {resolve(msg, g)}")
if any("{" in l or "}" in l for l in lines):
    bad = [l for l in lines if "{" in l or "}" in l][:5]
    raise SystemExit(f"unresolved markers, fix the sheet first: {bad}")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(rows)} sheet rows -> {len(lines)} opener lines ({n_marked} gender-marked rows x3) in {OUT.name}")
print(dict(collections.Counter(l.split("|")[0].strip() for l in lines)))

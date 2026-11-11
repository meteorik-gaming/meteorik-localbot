# CELL 8 -- read your rated .md files and update the dataset (Google Docs are not read: export the rated Doc as .md).
# 4-5 -> approved, 3 -> stays "unreviewed", 1-2 -> rejected, empty -> untouched.
# Works from the Drive files alone (cell 6 does NOT need to be run again): it reads approved/<batch>_en.jsonl.
# Set BATCHES in cell 0 to apply several batches at once, e.g. BATCHES = ["gran1", "spec1"]; without it, only BATCH.
# .md files: put them in Drive localbot-training/scores/ named review_<batch>_en_<anything>.md
# Output: Drive approved/<batch>_en_reviewed.jsonl and scores/review_<batch>_en_summary.json
import statistics


# a conversation starts at a line like "3 -- bot-en-p4-00012" (markdown "## " prefix)
HEAD = re.compile(r"^[ \t#]*\d+[ \t]*(?:--|–|—|\\-\\-)[ \t]*bot[\w\\-]+", re.M)


def split_blocks(text):
    marks = list(HEAD.finditer(text))
    return [text[m.start(): marks[k + 1].start() if k + 1 < len(marks) else len(text)] for k, m in enumerate(marks)]


def apply_batch(batch):
    prefix = f"review_{batch}_{LANG}_"
    texts = [(f.stem, 0, f.read_text(encoding="utf-8")) for f in sorted((BASE / "scores").glob(prefix + "*.md"))]
    print(f"\n=== {batch} === reading:", [n for n, _, _ in texts])
    if not texts:
        print(f"!! no {prefix}*.md in {BASE / 'scores'}")
        return

    src = BASE / "approved" / f"{batch}_{LANG}.jsonl"
    if not src.exists():
        print(f"!! {src} not found: run cell 6 for batch {batch} once.")
        return
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_id = {r["id"]: r for r in rows}

    ratings, notes, blocks = {}, [], []
    for _, _, text in texts:
        blocks += split_blocks(text)
    for block in blocks:
        mid = re.search(r"bot[\w\\-]+", block[:300])
        if not mid or "RATING" not in block:
            continue
        jid = mid.group(0).replace("\\", "")
        after = block.split("RATING", 1)[1].split("NOTES", 1)[0]
        after = after.split(":", 1)[1] if ":" in after else after
        mr = re.search(r"(?<![\w.])([1-5])(?![\w.])", after)
        if not mr:
            continue
        ratings[jid] = int(mr.group(1))
        mn = re.search(r"NOTES[^:\n]*:[ \t*]*([^\n]*)", block)
        note = mn.group(1).replace("\\", "").strip(" *\t\r") if mn else ""
        if note and set(note) != {"-"}:
            notes.append({"id": jid, "rating": int(mr.group(1)), "note": note})

    if not ratings:
        print("!! No ratings found: the number must come right after 'RATING (1-5):'.")
        for name, _, text in texts:
            print(f"   {name}: {len(text)} chars, RATING lines seen:")
            for line in [l for l in text.splitlines() if "RATING" in l][:6]:
                print("     ", repr(line))
        return
    missing = [i for i in ratings if i not in by_id]
    print(f"found {len(ratings)} ratings in {len(blocks)} conversations" + (f" ({len(missing)} ids not in {src.name})" if missing else ""))

    out = []
    for rid, row in by_id.items():
        rt = ratings.get(rid)
        review = "unreviewed" if rt is None else ("approved" if rt >= 4 else "rejected" if rt <= 2 else "unreviewed")
        out.append({**row, "review": review, "human_rating": rt})
    (BASE / "approved" / f"{batch}_{LANG}_reviewed.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out), encoding="utf-8")

    vals = list(ratings.values())
    summary = {"rated": len(vals), "average": round(statistics.mean(vals), 2), "histogram": {k: vals.count(k) for k in range(1, 6)},
               "approved": sum(1 for r in out if r["review"] == "approved"), "notes": notes}
    (BASE / "scores" / f"review_{batch}_{LANG}_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print({k: v for k, v in summary.items() if k != "notes"}, "-> approved/" + f"{batch}_{LANG}_reviewed.jsonl")


def _names(x):                      # accepts "a", ["a", "b"] or [["a", "b"]]
    return [x] if isinstance(x, str) else [n for item in x for n in _names(item)]


for b in _names(globals().get("BATCHES", BATCH)):
    apply_batch(b)
print("\n-> send the summaries (scores/review_<batch>_en_summary.json) to Claude: the notes tell it what to fix in the prompts.")

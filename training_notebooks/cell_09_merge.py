# CELL 9 -- merge the human-approved batches into ONE training set (Core ALLOWED, one language).
# Needs cells 1 and 3 only (cell 3 = the latest rules). Batches are NOT regenerated: every approved row is
# re-checked here with the current cell 3 rules, so rows you rated 4-5 that break a newer rule are dropped.
# Reads  approved/<batch>_<LANG>_reviewed.jsonl  (made by cell 8)  and keeps review == "approved".
# Writes train/core_allowed_<LANG>_train.jsonl, ..._val.jsonl (system = header, then the chat) and
#        train/core_allowed_<LANG>_dropped.jsonl + train/regen_<LANG>.jsonl + scores/merge_<LANG>_report.json
# v3 RECYCLE: old rows (v2 category names) are matched by their `opener` text against seeds/openers_<LANG>.txt (v3), their `special`
# is rewritten to the v3 name, and rows whose opener moved to a DIFFERENT behaviour (old hard_block / boundary_push lines now spicy or
# chat, nick lines now chat, ...) are NOT kept: they go to regen_<LANG>.jsonl so the generator can write them again. The optional
# seeds/opener_map_v2_to_v3.tsv is only read for the human reason (its `why` column) shown in that file.
import collections

MERGE = globals().get("MERGE_BATCHES", ["p8a", "p9", "p10", "gran1", "spec1", "spec2", "spec3"])
VAL_SHARE = 0.06
CAP_ROWS_PER_PHRASE = 4          # one 6-word phrase may appear in at most this many rows (stops stock lines)
CAP_ROWS_PER_BUBBLE = 2          # the same long bubble, at most this many times

OPENERS_V3 = BASE / "seeds" / f"openers_{LANG}.txt"
MAP_TSV = BASE / "seeds" / "opener_map_v2_to_v3.tsv"
OLD_TO_NEW = {"none": "chat", "general": "chat", "media": "pic", "honesty_sincere": "real", "honesty_playful": "chat",
              "hard_block": "block", "boundary_push": "push", "pixel_mean": "dog"}      # distress -> sad / sos (below); unsend, nick keep their names
NEW_NAMES = {"chat", "unsend", "pic", "push", "spicy", "real", "nick", "dog", "block", "sad", "sos"}
STABLE = {"chat", "unsend", "pic", "real", "sad", "sos"}      # kept even if their opener is gone from v3 (if they still pass the rules)
(BASE / "train").mkdir(exist_ok=True)


def norm_text(t):
    return re.sub(r"\s+", " ", str(t).strip().lower())


def load_v3():
    """opener text -> set of v3 categories (the v3 file is the truth for where an opener lives now)."""
    out = {}
    if not OPENERS_V3.exists():
        print("!! no v3 openers file:", OPENERS_V3.name, "(rows keep their old category, renamed)")
        return out
    for line in OPENERS_V3.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            parts = [x.strip() for x in line.split("|", 2)]
            if len(parts) == 3 and parts[2]:
                out.setdefault(norm_text(parts[2]), set()).add({"general": "chat"}.get(parts[0], parts[0]))
    return out


def load_reasons():
    """norm(old text) -> `why` from the map. Columns: old_category, old_tags, text, new_category, new_tags, why (found by header name)."""
    out = {}
    if not MAP_TSV.exists():
        return out
    rows = [l.split("\t") for l in MAP_TSV.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    head = [c.strip().lower() for c in rows[0]] if rows else []
    if "text" not in head or "why" not in head:
        print("!! opener map header not recognised (need text and why columns):", head)
        return out
    ti, wi = head.index("text"), head.index("why")
    for r in rows[1:]:
        if len(r) > max(ti, wi):
            out[norm_text(r[ti])] = r[wi].strip()
    return out


V3 = load_v3()
REASON = load_reasons()


def old_behaviour(r):
    sp = r.get("special", "chat")
    if sp == "distress":
        crisis = any("[crisis]" in m["content"] for m in r["messages"] if m["role"] == "assistant")
        return "sos" if crisis else "sad"
    return OLD_TO_NEW.get(sp, sp)


def recycle(r):
    """-> (row with the v3 special, None) to keep, (None, reason) to regenerate/drop."""
    old = old_behaviour(r)
    if old not in NEW_NAMES:
        return None, f"unknown old special {r.get('special')!r}"
    cats = V3.get(norm_text(r.get("opener", "")))
    if cats is None:
        if not V3 or old in STABLE:
            return {**r, "special": old}, None
        return None, f"opener gone from v3 ({old})"
    new = old if old in cats else ("chat" if old == "unsend" and "chat" in cats else None)
    if new is None:
        return None, f"opener moved {old} -> {'/'.join(sorted(cats))}"
    return {**r, "special": new}, None
re_tag9 = re.compile(r"\[mood: (\w+)\] \[affinity: (\w+)\] \[excitation: (\w+)\] \[boundary: (\w+)\]((?: \[[^\[\]]+\])*)$")


def turns_of(msgs):
    out, user = [], ""
    for m in msgs:
        if m["role"] != "assistant":
            user = m["content"]
            continue
        lines = m["content"].rstrip().split("\n")
        mt = re_tag9.search(lines[-1])
        if not mt:
            return None
        mood, aff, aro, bnd, rest = mt.groups()
        out.append({"user": user, "bot": [b for b in "\n".join(lines[:-1]).strip().split("\n\n") if b.strip()],
                    "mood": mood, "affinity": aff, "excitation": aro, "boundary": bnd, "actions": re.findall(r"\[[^\[\]]+\]", rest)})
    return out


def recheck(row):
    for m in row["messages"]:
        m["content"] = fix_player_tag(m["content"])
    if "busy" not in row["header"] or "busy:" not in row["header_text"]:
        return ["old header format (no busy)"]
    turns = turns_of(row["messages"])
    if not turns or any(not t["bot"] for t in turns):
        return ["unparseable"]
    why = list(extra_problems(turns, row["header"], row.get("special")))
    if flavor_problem(turns, row.get("flavor", True)):
        why.append("pet/plant/chair overuse")
    if any(re.search("[—–]", b) for t in turns for b in t["bot"]):
        why.append("long dash")
    return sorted(set(why))


kept, dropped, per_batch, regen = [], [], {}, []
for b in MERGE:
    src = BASE / "approved" / f"{b}_{LANG}_reviewed.jsonl"
    if not src.exists():
        print(f"!! {src.name} missing: run cell 8 for {b}")
        continue
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if r.get("review") == "approved"]
    n_keep = 0
    for old_row in ok:
        r, moved = recycle(old_row)
        if r is None:                          # the opener moved to another behaviour (or is gone): written again, not recycled
            regen.append({"id": old_row["id"], "batch": b, "old_special": old_row.get("special"), "opener": old_row.get("opener"),
                          "reason": moved, "map_reason": REASON.get(norm_text(old_row.get("opener", "")), "")})
            continue
        why = recheck(r)
        if why:
            dropped.append({"id": r["id"], "reasons": why, "row": r})
        else:
            kept.append(r)
            n_keep += 1
    per_batch[b] = {"rated_approved": len(ok), "kept_after_recheck": n_keep}

# cross-batch repetition guard (hard blocks are short on purpose, so they are exempt)
phrase_rows, bubble_count, final = collections.Counter(), collections.Counter(), []
for r in kept:
    if r.get("special") == "block":
        final.append(r)
        continue
    bubbles = [x for t in turns_of(r["messages"]) for x in t["bot"]]
    grams = set().union(*[shingles(x, 6) for x in bubbles])
    long_b = [x for x in bubbles if len(x.split()) >= 4]
    if any(phrase_rows[g] >= CAP_ROWS_PER_PHRASE for g in grams) or any(bubble_count[x] >= CAP_ROWS_PER_BUBBLE for x in long_b):
        dropped.append({"id": r["id"], "reasons": ["repeated phrase across batches"], "row": r})
        continue
    for g in grams:
        phrase_rows[g] += 1
    for x in long_b:
        bubble_count[x] += 1
    final.append(r)

# train / val split, seeded; every special gets some validation rows
rng = random.Random(42)
rng.shuffle(final)
val, train, seen_special = [], [], collections.Counter()
n_val = max(1, round(len(final) * VAL_SHARE))
for r in final:
    sp = r.get("special", "chat")
    if len(val) < n_val and (seen_special[sp] < 2 or rng.random() < VAL_SHARE):
        val.append(r)
        seen_special[sp] += 1
    else:
        train.append(r)


def to_chat(r):
    return {"id": r["id"], "special": r.get("special"),
            "messages": [{"role": "system", "content": r["header_text"]}] + r["messages"]}


for name, rows in (("train", train), ("val", val)):
    (BASE / "train" / f"core_allowed_{LANG}_{name}.jsonl").write_text(
        "\n".join(json.dumps(to_chat(r), ensure_ascii=False) for r in rows), encoding="utf-8")
(BASE / "train" / f"core_allowed_{LANG}_dropped.jsonl").write_text(
    "\n".join(json.dumps(d, ensure_ascii=False) for d in dropped), encoding="utf-8")
(BASE / "train" / f"regen_{LANG}.jsonl").write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in regen), encoding="utf-8")

report = {"batches": per_batch, "approved_total": sum(v["rated_approved"] for v in per_batch.values()),
          "dropped_by_recheck": len(dropped), "to_regenerate": len(regen),
          "regen_reasons": collections.Counter(d["reason"] for d in regen).most_common(), "train": len(train), "val": len(val),
          "drop_reasons": collections.Counter(x for d in dropped for x in d["reasons"]).most_common(),
          "specials_train": collections.Counter(r.get("special", "chat") for r in train),
          "assistant_turns": sum(len(r["messages"]) // 2 for r in train)}
(BASE / "scores" / f"merge_{LANG}_report.json").write_text(json.dumps(report, indent=1, default=dict), encoding="utf-8")
print(json.dumps(report, indent=1, default=dict))
print("\n-> train/core_allowed_%s_train.jsonl is what the training cell (10) reads. Send me merge_%s_report.json." % (LANG, LANG))

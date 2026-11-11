import collections
import csv
import os
# CELL 12 -- turn the REVIEWED reply sheet into training rows (single turns). The teacher does NOT write anything here:
# Bot's reply is your sheet text, word for word. The teacher only LABELS it (mood / affinity / excitation / boundary / actions),
# then the code builds a header that agrees with those labels and with the row's tags (near / day / hi / hot / +ctx).
#
# Run order (GPU runtime, same session): cells 1, 2, 3, 4 (skip if profiles exist), then cell 5 with WEB_MODE = True set first
# (that only loads cell 5's functions, it generates nothing), then THIS cell, then cell 6.
# Needs in Drive seeds/: reply_sheet.csv (en) or reply_sheet_es.csv (es), the same sheet the openers came from.
# Cell 0 variables: BATCH = "sheet1" (any new name), RATING = "allowed" (the restricted column is not used), LANG.
#   SHEET_LIMIT = 20      first look: labels only 20 rows spread over all categories (read them in cell 6). None = the whole sheet.
#   SHEET_CATS = None     or a list like ["chat", "spicy"] to do some categories only.
# Writes drafts/<BATCH>_<LANG>.jsonl. Rerun after a disconnect: it skips finished ids. After it: cell 6, then cell_12b (approve), then cell 9.
import threading
import time
from concurrent.futures import ThreadPoolExecutor

SHEET_LIMIT = globals().get("SHEET_LIMIT", None)
SHEET_CATS = globals().get("SHEET_CATS", None)
assert RATING == "allowed", "cell 12 uses the allowed reply column; the RESTRICTED pack is trained later"
assert "DRAFTS" in globals() and "sample_axes" in globals(), "run cell 5 first with WEB_MODE = True (it only loads the functions)"

SHEET = BASE / "seeds" / ("reply_sheet_es.csv" if LANG == "es" else "reply_sheet.csv")
assert SHEET.exists(), f"upload {SHEET.name} to Drive seeds/"
MARKER = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}")
TG = h.SPEC["tags"]
LABEL_BOND_AFF = BOND_AFF                                   # cell 3: which affinity ranks each bond allows
MOOD_VALENCE = {"happy": ("pleasant", "joyful"), "annoyed": ("foul", "sour"), "calm": ("neutral", "pleasant"),
                "neutral": ("neutral", "pleasant", "sour"), "alert": tuple(B["valence"])}
MEDIA_IDS = "[img: selfie] [img: pet] [img: food] [img: plant] [img: outfit] [gif: laugh] [gif: blush] [gif: hug] [gif: wink] [gif: pout] [gif: wave] [vid: petZoomies]"
CAT_HINT = {
    "chat": "Normal chat. boundary none. actions [] unless her words clearly send a picture or gif (then exactly one media action).",
    "pic": f"A picture or gif is involved: actions MUST be exactly ONE media action that matches the player's request and her line, from: {MEDIA_IDS}. "
           "[img: pet] only if a pet is the subject; [img: food] only for food; [gif: wink] only if she is clearly flirting.",
    "nick": "She coins a nickname in her reply: actions = [nick: <that nickname as ONE lowercase word taken from her words>].",
    "spicy": "The customer made an out-of-scope or inappropriate ask and the assistant redirects. boundary is none or mild, NEVER severe. actions [].",
    "push": "The player pushed past a limit. boundary is mild or severe, never none. actions [].",
    "dog": "The player was mean about her pet. boundary is severe. actions [].",
    "block": "A hard no. boundary severe, excitation none, actions [].",
    "real": "She answers a sincere question about being an AI. mood calm, excitation none, boundary none, actions [].",
    "sad": "The player is sad. mood calm, excitation none, boundary none, actions [].",
    "sos": "The player may be in crisis. mood calm, excitation none, boundary none (the code adds the crisis action).",
}
LABEL_SYSTEM = (
    "You label chat replies for a training set. Bot, a texting persona, ALREADY wrote the reply: you never rewrite or judge it, you only describe it. "
    "Reply with ONE JSON object and nothing else: "
    '{"mood":"...","affinity":"...","excitation":"...","boundary":"...","actions":[]}. '
    f"mood is one of {', '.join(TG['mood'])} (how Bot sounds in THIS reply). affinity is one of {', '.join(TG['affinity'])} (how she feels about the player in this reply). "
    f"excitation is one of {', '.join(TG['excitation'])} (how turned on she sounds; most replies are none, only flirty ones go higher). "
    f"boundary is one of {', '.join(TG['boundary'])} (none = no limit set, mild = a firm no or pushback, severe = a hard stop or she turns cold). "
    "actions is a list of strings written exactly like \"[img: selfie]\", \"[gif: laugh]\", \"[nick: dummy]\" or []. Use only those exact tag words.")


def label_prompt(cat, user, bubbles, problems_txt=""):
    bot = "\n".join(f"- {b}" for b in bubbles)
    return (f"CATEGORY: {cat}. {CAT_HINT[cat]}\n\nPLAYER TEXTED: {user}\n\nBOT REPLIED (bubbles):\n{bot}\n\n"
            + (f"Your previous labels were rejected for: {problems_txt}. Fix them.\n\n" if problems_txt else "") + "JSON only.")


def read_label(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    t = json.loads(raw, strict=False)
    return {"mood": str(t.get("mood", "neutral")).lower(), "affinity": str(t.get("affinity", "neutral")).lower(),
            "excitation": str(t.get("excitation", "none")).lower(), "boundary": str(t.get("boundary", "none")).lower(),
            "actions": [norm_action(a) for a in t.get("actions", []) if str(a).strip()]}


def force_label(lab, cat):
    """What the category fixes by itself, whatever the teacher said."""
    if lab["mood"] not in TG["mood"]:
        lab["mood"] = "neutral"
    if lab["affinity"] not in TG["affinity"]:
        lab["affinity"] = "neutral"
    if lab["excitation"] not in TG["excitation"]:
        lab["excitation"] = "none"
    if lab["boundary"] not in TG["boundary"]:
        lab["boundary"] = "none"
    if cat == "block":
        lab.update(boundary="severe", excitation="none", actions=[])
    elif cat == "sos":
        lab.update(excitation="none", boundary="none", actions=["[crisis]"])
    elif cat in ("sad", "real"):
        lab.update(excitation="none", boundary="none", actions=[])
    elif cat == "spicy" and lab["boundary"] == "severe":
        lab["boundary"] = "mild"
    elif cat == "push" and lab["boundary"] == "none":
        lab["boundary"] = "mild"
    elif cat == "dog":
        lab["boundary"] = "severe"
    if cat not in ("pic", "nick", "chat"):
        lab["actions"] = [a for a in lab["actions"] if a == "[crisis]"]
    return lab


def header_for(r, cat, tags, ctx, lab, bubbles, reply_txt):
    """A header that agrees with the labels (valence <- mood, bond <- affinity, heat <- excitation), the row's tags/context,
    and the bubble shape (bubble_limits). None when nothing fits in 600 tries."""
    aff_i = AFF_ORDER.index(lab["affinity"])
    for _ in range(600):
        v = sample_axes(r)
        if v["valence"] not in MOOD_VALENCE[lab["mood"]]:
            continue
        lo, hi = LABEL_BOND_AFF[v["bond"]]
        if not lo <= aff_i <= hi:
            continue
        if cat not in FREE_SPECIALS and lab["excitation"] not in HEAT_EXCITATION[v["heat"]]:
            continue
        if cat == "nick" and v["bond"] not in ("close", "devoted"):
            continue
        match = [p for p in profiles if all(p["sliders"][k] == v[k] for k in ("distance", "dominance", "openness"))]
        prof = r.choice(match or profiles)
        v["distance"], v["dominance"], v["openness"] = (prof["sliders"][k] for k in ("distance", "dominance", "openness"))
        hour = r.uniform(0, 24)
        v["busy"] = sample_busy(r, h.time_band(hour))
        vals = {"v": "2", "mode": "chat", "rating": RATING, "persona": "bot", "lang": LANG,
                "lore": prof["lore"], "job": prof["job"], "friends": friends_line(prof["friends"]),
                "time": h.time_band(hour), **sample_lists(r, v["bond"]), **v}
        apply_home_pet(vals, prof)
        if LANG == "es":
            g = r.choices(["male", "female", "unspecified"], [40, 40, 20])[0]
            vals["player"] = "" if g == "unspecified" else f"The user's gender is {g}."
        if not (all(tag_ok(t, vals) for t in tags) and ctx_ok(ctx, vals)):
            continue
        if "Pixel" in reply_txt and "Pixel" not in vals.get("pet", ""):
            continue
        if cat not in ("real", "sad", "sos"):
            blo, bhi, maxw = bubble_limits(vals)
            if vals["intensity"] == "flood" or not (blo <= len(bubbles) <= bhi) or any(len(b.split()) > maxw for b in bubbles):
                continue
        vals["header_text"] = h.render(vals)
        return vals
    return None


sheet = [x for x in csv.DictReader(open(SHEET, encoding="utf-8-sig", newline="")) if x["category"].strip() in OPENER_CATS
         and (SHEET_CATS is None or x["category"].strip() in SHEET_CATS) and x["message"].strip() and x["reply_allowed"].strip()]
random.Random(7).shuffle(sheet)                      # stable order: a small first look covers every category, the full run skips what is done
if SHEET_LIMIT:
    sheet = sheet[:SHEET_LIMIT]
old = [json.loads(l) for l in DRAFTS.read_text(encoding="utf-8").splitlines() if l.strip()] if DRAFTS.exists() else []
good_old = [x for x in old if "error" not in x and x.get("source") == "sheet"]
if len(good_old) != len(old):                       # error rows (and rows from another source) are dropped, so a rerun retries them
    print(f"dropping {len(old) - len(good_old)} old error/non-sheet rows from {DRAFTS.name} to retry them")
    DRAFTS.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in good_old), encoding="utf-8")
done = {x["id"] for x in good_old}
lock, progress, t0 = threading.Lock(), {"n": 0}, time.time()


def resolve(text, g):
    return MARKER.sub(lambda m: m.group(2) if g == "female" else m.group(1), text)


def make_row(x):
    sid = x["id"].strip()
    ex_id = f"bot-{LANG}-{BATCH}-{sid}"
    if ex_id in done:
        return
    cat = x["category"].strip()
    parsed = parse_tags(x["tags"])
    if parsed is None:
        out = {"id": ex_id, "error": f"unknown tag in {x['tags']!r}", "special": cat}
    else:
        tags, label, ctx = parsed
        r = random.Random(f"{BATCH}-{sid}")
        msg0 = clean(resolve(x["message"].strip(), "male"))                          # labeling only; the final text is resolved below
        bubbles0 = [clean(b) for b in re.split(r"\s*//\s*", resolve(x["reply_allowed"].strip(), "male")) if b.strip()]
        best, err, why = None, None, ""
        hot_tag = any(t == "intense" for t in tags)                                      # `hot` = heat flushed or above, which can't carry excitation "none"
        for attempt in range(3):
            try:
                lab = force_label(read_label(ask(LABEL_SYSTEM, label_prompt(cat, msg0, bubbles0, why), temperature=0.2 + 0.4 * attempt, max_tokens=200)), cat)
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:160]}"
                continue
            if hot_tag and lab["excitation"] == "none" and cat not in FREE_SPECIALS:
                lab["excitation"] = "mild"
            vals = header_for(r, cat, tags, ctx, lab, bubbles0, " ".join(bubbles0))
            if vals is None:
                err = "no header fits the labels, tags and bubble shape"
                continue
            g = es_player_gender(vals) if LANG == "es" else "male"
            msg = clean(resolve(x["message"].strip(), g))
            bubbles = [clean(b) for b in re.split(r"\s*//\s*", resolve(x["reply_allowed"].strip(), g)) if b.strip()]
            cand = {"user": msg, "bot": bubbles, **lab}
            postprocess(cand, [], vals, cat)                                          # excitation vs heat, wink rule
            best = (vals, cand, msg, label)
            bad = problems([cand], vals, cat)
            if not bad:
                break
            why = ", ".join(bad)
        if best is None:
            out = {"id": ex_id, "error": err or "labeling failed", "special": cat}
        else:
            vals, cand, msg, label = best
            out = {"id": ex_id, "format_version": 1, "rating": RATING, "mode": "chat", "persona": "bot", "lang": LANG,
                   "header": {k: v for k, v in vals.items() if k != "header_text"}, "header_text": vals["header_text"],
                   "special": cat, "flavor": True, "opener": msg, "opener_label": label, "sheet_id": sid,
                   "messages": [{"role": "user", "content": msg}, {"role": "assistant", "content": assistant_text(cand)}],
                   "source": "sheet", "teacher": TEACHER, "review": "unreviewed"}
    with lock, open(DRAFTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
        progress["n"] += 1
        if "error" in out and progress["n"] <= 3:
            print("!! ", out["id"], "->", out["error"], flush=True)          # the first errors show up right away, no need to wait for the summary
        if "error" in out:
            progress["err"] = progress.get("err", 0) + 1
        n, total = progress["n"], progress["total"]
        mins = (time.time() - t0) / 60
        left = max(total - n, 0)
        if n % 5 == 0 or left == 0:                                                  # one line that updates in place (Colab honours \r)
            bar = "#" * int(30 * n / max(total, 1))
            print(f"\r[{bar:<30}] {n}/{total} ({100 * n / max(total, 1):.0f}%) | {mins:.1f} min, ~{mins / n * left:.0f} min left | errors {progress.get('err', 0)}   ",
                  end="\n" if left == 0 else "", flush=True)


todo_count = len([y for y in sheet if f'bot-{LANG}-{BATCH}-{y["id"].strip()}' not in done])
progress["total"] = todo_count
print(len(sheet), "sheet rows to label (", len(sheet) - todo_count, "already done ) ->", DRAFTS)
with ThreadPoolExecutor(int(os.environ.get("OLLAMA_NUM_PARALLEL", "6"))) as pool:
    list(pool.map(make_row, sheet))
rows = [json.loads(l) for l in DRAFTS.read_text(encoding="utf-8").splitlines() if l.strip()]
errs = [x["error"] for x in rows if "error" in x]
print(len(rows), "rows,", len(errs), "errors;", dict(collections.Counter(x.get("special") for x in rows)))
for e, c in collections.Counter(errs).most_common(5):
    print("  ", c, "x", e)
print("next: cell 6 (same BATCH), read its 5 samples, then SHEET_STEP = \"approve\" and rerun this cell.")

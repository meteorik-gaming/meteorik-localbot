import re
# CELL 5 -- generate conversations, ONE Bot turn at a time. Resumable: rerun and it skips finished ids.
# The player's first line comes from YOUR openers file (cell 4b); later player lines are written by the teacher
# with the situation (distance, time) and the chat in view. Output: Drive drafts/<BATCH>_en.jsonl (raw).
import threading
import time
from concurrent.futures import ThreadPoolExecutor

DRAFTS = BASE / "drafts" / f"{BATCH}_{LANG}.jsonl"
PROFILES = BASE / "seeds" / f"profiles_{LANG}.jsonl"      # made by cell 4 (skip cell 4 when it exists)
OPENERS = BASE / "seeds" / f"openers_{LANG}.txt"          # made by cell 4b
profiles = [json.loads(l) for l in PROFILES.read_text(encoding="utf-8").splitlines() if l.strip()]
profiles = [p for p in profiles if not CJK_RE.search(p["lore"] + p["job"])]       # a stray Chinese character in a backstory
done = set()
if DRAFTS.exists():
    done = {json.loads(l)["id"] for l in DRAFTS.read_text(encoding="utf-8").splitlines() if l.strip()}
lock = threading.Lock()
progress, t0 = {"n": 0}, time.time()      # one line per finished conversation, so you can see it moving

BANK_SPECIALS = ("real", "sad", "sos", "push", "dog", "nick", "block", "spicy")      # the special applies to turn 1, the opener decides it
OPENER_CATS = BANK_SPECIALS + ("pic", "chat")                                      # unsend uses chat lines; pic is handled below
OLD_TAGS = {"far": "!near", "late": "!day", "flirt": "intense", "intimate": "hi"}                   # v2 tag names, still readable
_BASE_TAG = {
    "near": lambda v: v["distance"] in ("cohabiting", "together", "nearby"),
    "day": lambda v: v["time"] in ("morning", "afternoon"),
    "hi": lambda v: v["bond"] in ("warm", "close", "devoted"),
    "intense": lambda v: v["heat"] in ("engaged", "intense", "maximal"),
}


def tag_ok(tag, v):
    """v3 tags: near / day / hi / hot, `!` negates (!near = remote or apart, !day = evening, night, small hours,
    !hi = cold or wary, !hot = dormant or mild). `@label` is a pool label: no effect in ALLOWED."""
    tag = OLD_TAGS.get(tag, tag)
    neg = tag.startswith("!")
    return _BASE_TAG[tag.lstrip("!")](v) != neg


# `+name` = context tag: the line only goes with a profile whose lore or job contains one of these words.
# Tag by job / situation (not by scenario name) so new scenarios and mods reuse them. Add a row to add a tag.
CTX_WORDS = {
    "animals": r"\b(dogs?|cats?|chickens?|hens?|horses?|cows?|animals?|pets?|puppy|kitten|malinois|greyhound|husky|pug|retriever|tabby|rabbit|parrot|doberman|borzoi|mutt|whippet|shepherd)\b",
    "farm": r"\b(farm|farmer|farmhouse|harvest|barn|farmers'? market|weekend market|chickens?|hens?|garden|crops?)\b",
    "shift_work": r"\b(waitress|waiter|diner|nurse|barista|shift|shifts|tips|cashier|bartender)\b",
    "studio_work": r"\b(model|influencer|studio|photograph\w*|shoot|shoots|brand deals?)\b",
    "travel_stay": r"\b(for a few weeks|back in (the )?(city|town)|in town|travel\w*|visiting|nomad)\b",
    "roommate": r"\b(roommate|flatmate|shares a (cramped )?flat)\b",
    "family": r"\b(family|sister|brother|mom|dad|mother|father|grandmother|grandma)\b",
    "online": r"\b(streamer|streams?|online|gamer|gaming|twitch)\b",
    "office": r"\b(office|firm|team[- ]lead|coworkers?|colleagues?|analyst|boss|promotion)\b",
    "night_shift": r"\b(night[- ]shift|bartender|regulars|closing time|nightlife|the bar)\b",
    "sport": r"\b(cycl\w*|bikes?|rides?|running|runner|gym|sporty|athlet\w*|trainer)\b",
    "married": r"\b(married|marriage|spouse|husband|wife)\b",
    "finance": r"\b(trader|finance|stocks?|salary|paycheck|bonus|wall street|the market)\b",
    "party": r"\b(party|parties|partying|hangovers?|clubbing|nightclub|bad crowd|heavy drinking)\b",
    "dog": DOG_SPECIES_RE.pattern,                                  # read from the header's `pet` line
    "cat": r"\b(cats?|kittens?|tabby)\b",
    "pet": r".",                                                    # any pet at all (the `pet` line is not empty)
    "male": r"gender is male",                                      # ES openers with {masc|fem} markers (cell 11): read from the `player` line
    "female": r"gender is female",
}
FIELD_OF = {"dog": "pet", "cat": "pet", "pet": "pet", "male": "player", "female": "player"}               # these tags look only at that header field; the rest search lore + job + home + pet


def ctx_ok(ctx, vals):
    """Every `+x` must be present in the profile, every `!+x` must be absent."""
    text = " ".join(vals.get(k, "") for k in ("lore", "job", "home", "pet")).lower()
    for c in ctx:
        neg = c.startswith("!")
        c = c.lstrip("!")
        hit = bool(re.search(CTX_WORDS[c], vals.get(FIELD_OF[c], "").lower() if c in FIELD_OF else text))
        if hit == neg:
            return False
    return True


def parse_tags(raw):
    """-> (tags, label, ctx) or None when a tag is unknown."""
    tags, label, ctx = [], None, []
    for t in (x.strip() for x in raw.split(",")):
        if t in ("", "-"):
            continue
        if t.startswith("@"):
            label = t[1:].strip() or None
        elif t.startswith("+") or t.startswith("!+"):               # +x = needs x in the profile; !+x = must NOT have x
            if t.lstrip("!+") not in CTX_WORDS:
                return None
            ctx.append(("!" if t[0] == "!" else "") + t.lstrip("!+"))
        elif OLD_TAGS.get(t, t).lstrip("!") in _BASE_TAG:
            tags.append(t)
        else:
            return None
    return tags, label, ctx


# openers_<lang>.txt always; openers_<lang>_restricted.txt only with RATING == "restricted" (its lines are the RESTRICTED-only ones)
opener_files = [OPENERS] + sorted(OPENERS.parent.glob(f"openers_{LANG}_extra*.txt")) + ([OPENERS.with_name(f"openers_{LANG}_restricted.txt")] if RATING == "restricted" else [])
openers = []
for path in opener_files:
    if not path.exists():
        print("openers file missing:", path.name)
        continue
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() and not line.startswith("#"):
            parts = [p.strip() for p in line.split("|", 2)]
            cat = {"general": "chat"}.get(parts[0], parts[0])            # v2 name still readable
            parsed = parse_tags(parts[1]) if len(parts) == 3 else None
            if parsed is None or not parts[2] or cat not in OPENER_CATS:
                print(f"{path.name} line {n} skipped (needs: category | tags | text; categories {list(OPENER_CATS)}; tags near/day/hi/hot, `!` negates, @label, +context): {line[:60]}")
                continue
            openers.append({"cat": cat, "tags": parsed[0], "label": parsed[1], "ctx": parsed[2], "text": parts[2]})
print(len(openers), "openers:", dict(__import__("collections").Counter(o["cat"] for o in openers)))


def pick_opener(r, special, vals):
    cat = special if special in BANK_SPECIALS else "chat"
    if special == "pic" and r.random() < 0.6:            # 60%: the player asks for a pic/gif; else Bot sends one on her own (a chat line)
        cat = "pic"
    pool = [o for o in openers if o["cat"] == cat and all(tag_ok(t, vals) for t in o["tags"]) and ctx_ok(o["ctx"], vals)]
    if not pool and cat == "pic":                          # no pic line in the file fits: a chat one, Bot sends on her own
        pool = [o for o in openers if o["cat"] == "chat" and all(tag_ok(t, vals) for t in o["tags"]) and ctx_ok(o["ctx"], vals)]
    return r.choice(pool) if pool else None


def clean(s):
    """Plain apostrophes / quotes, one line of spaces: the model should not learn curly quotes."""
    s = str(s).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("…", "...")
    return fix_player_tag(re.sub(r"\s*[—–]\s*", ", ", s).strip())      # no long dashes (Sam, review p4); one name placeholder


PET_NAMES_ALL = sorted({n for p, _ in PET_POOL for n in pet_names(p)})


def fix_case(b):
    """Normal capitalization (the maintainer's review, 2026-10-24): sentence starts, "I", and pet names."""
    b = re.sub(r"\bi\b", "I", b)
    for name in PET_NAMES_ALL:
        b = re.sub(r"\b" + name + r"\b", name, b, flags=re.I)
    return re.sub(r"(^|(?<!\.\.)[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), b)      # not after "..."


def norm_action(a):
    """The teacher sometimes drops the brackets ("crisis"), the space ("img:selfie") or sends an object ({"nick": "dummy"}):
    the tag line needs "[crisis]", "[img: selfie]", "[nick: dummy]"."""
    if isinstance(a, dict) and a:
        k, v = next(iter(a.items()))
        a = f"{k}: {v}"
    a = re.sub(r"^(img|gif|vid|nick):(?=\S)", r"\1: ", str(a).strip().strip("[]").strip())
    return f"[{a}]"


def repair(cand, turns, vals, special):
    """Fixes the code can make by itself instead of rejecting: a wink where it does not belong, and a second reply
    that starts with the player's name again."""
    wink_ok = vals["heat"] not in ("dormant", "mild") and special not in ("push", "block", "dog", "sad", "sos", "real") \
        and not any(WINK in b for t in turns for b in t["bot"])
    if not wink_ok:
        cand["bot"] = [re.sub(r"\s*" + WINK, "", b).strip() or b for b in cand["bot"]]
    if special != "nick" and random.random() < 0.7:        # p9: the teacher put the name in ~80% of the chats, a person uses it now and then (target 0.2-0.3 per chat)
        for k, b in enumerate(cand["bot"]):
            nb = re.sub(r"^\{player\}[,.!?]*\s*", "", b)
            nb = re.sub(r",?\s*\{player\}(?=[.!?]*$)", "", nb)
            nb = re.sub(r",\s*\{player\},", ",", nb)
            if nb and "{player}" not in nb and nb != b:
                cand["bot"][k] = fix_case(nb)
    if any(t["bot"] and t["bot"][0].lower().startswith("{player}") for t in turns):
        first = re.sub(r"^\{player\}[,.!?]*\s*", "", cand["bot"][0])
        if first:
            cand["bot"][0] = first[0].upper() + first[1:]


def parse_turn(raw, user):
    """Tolerant JSON read of ONE Bot reply: code fences, a bare string instead of a list, missing keys."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
    t = json.loads(raw, strict=False)
    bot = t.get("bot", [])
    if isinstance(bot, str):
        bot = [b for b in bot.split("\n\n") if b.strip()]
    bot = [fix_case(clean(b)) for b in bot if str(b).strip()]
    if not bot:
        raise ValueError("no bubbles")
    return {
        "user": user, "bot": bot,
        "mood": str(t.get("mood", "neutral")).lower(), "affinity": str(t.get("affinity", "neutral")).lower(),
        "excitation": str(t.get("excitation", "none")).lower(), "boundary": str(t.get("boundary", "none")).lower(),
        "actions": [norm_action(a) for a in t.get("actions", []) if str(a).strip()],
    }


def assistant_text(turn):
    """The exact assistant message the model must learn: bubbles, then the tag line (TRAINING_RULES 3)."""
    tags = f"[mood: {turn['mood']}] [affinity: {turn['affinity']}] [excitation: {turn['excitation']}] [boundary: {turn['boundary']}]"
    acts = "".join(f" {a}" for a in turn.get("actions", []))
    bubbles = "\n\n".join(b.strip() for b in turn["bot"] if str(b).strip())
    return (bubbles + "\n" if bubbles else "") + tags + acts


def history_lines(turns):
    out = []
    for t in turns:
        out.append("Player: " + t["user"])
        out.extend("Bot: " + b for b in t["bot"])      # one line per bubble (a " / " join got copied into the replies)
    return out


def make_player(turns, vals, r, nudge=""):
    """The teacher writes the player's next line, knowing the situation. None if it keeps failing."""
    seen = {t["user"].lower() for t in turns}
    for _ in range(3):
        try:
            raw = ask(PLAYER_SYSTEM, player_prompt(history_lines(turns), vals, nudge), temperature=1.0, max_tokens=150)
            text = clean(json.loads(raw, strict=False)["player"])
        except Exception:
            continue
        if 0 < len(text.split()) <= 30 and not re.search(r"[{}\[\]<>]", text) and text.lower() not in seen:
            return text
    return None


def postprocess(cand, turns, vals, special_turn):
    """What the code fixes by itself on a parsed teacher reply (shared by the local teacher and the web import)."""
    if special_turn == "block":                       # fixed by rule, whatever the teacher wrote
        cand.update(boundary="severe", excitation="none", actions=[])
    elif special_turn not in FREE_SPECIALS:
        cand["excitation"] = clamp_excitation(cand["excitation"], vals["heat"])
    repair(cand, turns, vals, special_turn)
    return cand


def make_bot(turns, user, vals, special_turn, flavor, flavor_used, shape, tone):
    """One Bot reply; ask again (up to 3 times) while a rule check fails. Returns (turn or None, last error)."""
    best, err = None, None
    for _ in range(3):
        try:
            prompt = turn_prompt(vals["header_text"], history_lines(turns), user, with_pet(SPECIAL_TEXT[special_turn], vals), shape,
                                 tone, flavor and not flavor_used, LANG, vals)
            cand = parse_turn(ask(with_pet(IDENTITY, vals), prompt, temperature=0.9, max_tokens=1200), user)
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:160]}"
            continue
        postprocess(cand, turns, vals, special_turn)
        best = cand
        if not problems(turns + [cand], vals, special_turn, flavor):
            break               # clean; otherwise ask again, and the last try is kept for cell 6 to judge
    return best, err


def setup_example(i):
    """Everything about conversation i that is decided BEFORE any teacher call (deterministic per batch name and i):
    the header, the special, the opener, how many turns, which special each turn carries and its shape."""
    ex_id = f"bot-{LANG}-{BATCH}-{i:05d}"
    r = random.Random(f"{BATCH}-{i}")      # the batch name is part of the seed, so a new batch never repeats an old one's setups
    v = sample_axes(r)
    # profile whose sliders match the sampled ones when possible, else any (lore is flavor, sliders rule)
    match = [p for p in profiles if all(p["sliders"][k] == v[k] for k in ("distance", "dominance", "openness"))]
    prof = r.choice(match or profiles)
    v["distance"], v["dominance"], v["openness"] = (prof["sliders"][k] for k in ("distance", "dominance", "openness"))
    special = sample_specials(r, v["bond"])
    hour = r.uniform(0, 24)
    v["busy"] = sample_busy(r, h.time_band(hour))
    vals = {"v": "2", "mode": "chat", "rating": RATING, "persona": "bot", "lang": LANG,
            "lore": prof["lore"], "job": prof["job"], "friends": friends_line(prof["friends"]),
            "time": h.time_band(hour), **sample_lists(r, v["bond"]), **v}
    apply_home_pet(vals, prof)                          # header lines `home` (blank = apartment) and `pet` (blank = none)
    if LANG == "es":                                    # the game's `player` line: ~40% male, 40% female, 20% unspecified (line omitted)
        g = r.choices(["male", "female", "unspecified"], [40, 40, 20])[0]
        vals["player"] = "" if g == "unspecified" else f"The user's gender is {g}."
    # the dog special pairs only with +dog / +cat openers (pick_opener); any other pet or none falls back to plain chat below
    header_text = h.render(vals)
    pick = pick_opener(r, special, vals)
    if pick is None:                                    # no human line fits this header/special: plain chat
        special, pick = "chat", pick_opener(r, "chat", vals)
    if pick is None:
        return {"id": ex_id, "error": "no opener fits", "special": special}
    n_turns = 1 if special == "block" else r.choices([1, 2, 3], [70, 20, 10])[0]      # one firm no, no second round
    special_at = r.randrange(n_turns) if special in ("pic", "unsend") and pick["cat"] != "pic" else 0     # a pic request is answered in turn 1
    flavor = special in ("dog", "pic") or r.random() < 0.25       # Pixel/plants/chair only in ~1 of 4
    sps = [special if (special in BANK_SPECIALS and ti == 0) or (special in ("sad", "sos")) or (special in ("pic", "unsend") and ti == special_at) else "chat"
           for ti in range(n_turns)]                                      # sad / sos keep their rules in every turn
    shapes = [turn_shape(r, v, sp) for sp in sps]
    return {"id": ex_id, "r": r, "v": v, "vals": {**vals, "header_text": header_text}, "header_text": header_text, "special": special,
            "pick": pick, "opener": pick["text"], "n_turns": n_turns, "flavor": flavor, "tone": tone_lines(v), "sps": sps, "shapes": shapes}


def build_row(st, turns):
    vals = {k: x for k, x in st["vals"].items() if k != "header_text"}
    return {
        "id": st["id"], "format_version": 1, "rating": RATING, "mode": "chat", "persona": "bot",
        "lang": LANG, "header": vals, "header_text": st["header_text"], "special": st["special"], "flavor": st["flavor"],
        "opener": st["opener"], "opener_label": st["pick"].get("label"),          # @label: no effect in ALLOWED, RESTRICTED binds it to into / uncomfortable / hard_limits
        "messages": [m for t in turns for m in (
            {"role": "user", "content": str(t["user"]).strip()},
            {"role": "assistant", "content": assistant_text(t)})],
        "source": "teacher", "teacher": TEACHER, "review": "unreviewed",
    }


def make_example(i):
    ex_id = f"bot-{LANG}-{BATCH}-{i:05d}"
    if ex_id in done:
        return
    st = setup_example(i)
    if "error" in st:
        with lock, open(DRAFTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(st) + "\n")
        return
    turns, error = [], None
    for ti in range(st["n_turns"]):
        if ti == 0:
            user = st["opener"]
        else:
            user = make_player(turns, st["vals"], st["r"])
            if user is None:
                error = "player line failed"
                break
        used = any(flavor_hit(b, st["vals"]) for t in turns for b in t["bot"])
        turn, err = make_bot(turns, user, st["vals"], st["sps"][ti], st["flavor"], used, st["shapes"][ti], st["tone"])
        if turn is None:
            error = err or "teacher failed"
            break
        turns.append(turn)
    row = build_row(st, turns) if turns else {"id": ex_id, "error": error or "no turns", "special": st["special"]}
    with lock, open(DRAFTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        progress["n"] += 1
        left = len([1 for k in range(N) if f"bot-{LANG}-{BATCH}-{k:05d}" not in done]) - progress["n"]
        mins = (time.time() - t0) / 60
        eta = mins / progress["n"] * max(left, 0)
        print(f"{progress['n']}/{progress['n'] + max(left, 0)} done, {mins:.1f} min, ~{eta:.0f} min left"
              + ("  (error row)" if "error" in row else ""), flush=True)


if not globals().get("WEB_MODE"):          # WEB_MODE = True (cell 5w) loads the functions above without calling the local teacher
    with ThreadPoolExecutor(int(os.environ.get("OLLAMA_NUM_PARALLEL", "6"))) as pool:     # as many as Ollama serves at once
        list(pool.map(make_example, range(N)))
    rows = [json.loads(l) for l in DRAFTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    errs = [r["error"] for r in rows if "error" in r]
    print(len(rows), "rows,", len(errs), "teacher/parse errors ->", DRAFTS)
    for e, c in __import__("collections").Counter(errs).most_common(5):
        print("  ", c, "x", e)

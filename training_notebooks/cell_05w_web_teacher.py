# CELL 5w -- the HOSTED teacher (Qwen 3.5 on its website, Apache 2.0). No API, no GPU, no `ask()`: you paste files into a Qwen
# project chat and save its answers as text files; this cell only WRITES the files to paste and READS the answers back.
#
# Qwen project setup, once:
#   * PROJECT SYSTEM PROMPT     -> paste training_notebooks/TEACHER_QWEN_SYSTEM_PROMPT.md
#   * PROJECT INSTRUCTIONS FILE -> upload web/<BATCH>/TEACHER_INSTRUCTIONS.md   (WEB_ACTION = "instructions"; built from cell 3, so it
#                                  always matches what the validators check; regenerate it whenever cell 3 changes)
#
# Run order: cells 0, 1, 3, 4, 4b, then set  WEB_MODE = True  and run cell 5 (it only loads functions), then this cell with:
#
#  A) NEW OPENERS (grow the opener file toward the v3 targets)
#     WEB_ACTION = "openers_prompt"  -> web/openers/prompt_NN.md : paste ONE per Qwen message; each asks for ~OPENERS_PER_MESSAGE lines
#     (save each answer as a .txt in web/openers/answers/)
#     WEB_ACTION = "openers_import"  -> checks every line (category, tags, duplicates, forbidden characters) and appends the good ones to
#                                       seeds/openers_<LANG>_extra_qwen.txt, which cell 5 reads next to the main openers file
#  B) DIALOGS (the whole chat in one go: openers come from the openers files, Bot's replies from Qwen)
#     WEB_ACTION = "export"  -> web/<BATCH>/requests/req_NNN.md : paste ONE per Qwen message (CHUNK chats each)
#     (save each answer as a file in web/<BATCH>/answers/ : any name, .json / .txt / .md, code fences are fine)
#     WEB_ACTION = "import"  -> same checks as cell 5; good chats go to drafts/<BATCH>_<LANG>.jsonl, bad ones are exported again
#                               (3 tries, the 3rd is kept for cell 6 to judge). When export says "nothing pending", run cell 6.
import collections
import time

WEB_ACTION = globals().get("WEB_ACTION", "export")
TEACHER = globals().get("TEACHER", "qwen3.5-web")          # recorded in every row
CHUNK = 8                                   # chats per pasted file; lower it if Qwen cuts its answer short
OPENERS_PER_MESSAGE = 100                   # opener lines per pasted prompt; Qwen can usually do 100 to 500 per answer, raise it if yours does
OPENERS_PER_CATEGORY_MESSAGE = 60           # at most this many of one category in one message (variety)
TARGETS = {"chat": 3000, "sos": 150, "sad": 150, "dog": 80, "real": 120, "nick": 100, "spicy": 600, "push": 400, "pic": 250, "block": 200}
PRIORITY = ["sos", "sad", "dog", "real", "nick", "spicy", "push", "pic", "block", "chat"]       # openers v3 handoff: 1, 1, 1, 2, 2, 2, 3, 3, 3, 4

WEB = BASE / "web" / BATCH
(WEB / "requests").mkdir(parents=True, exist_ok=True)
(WEB / "answers" / "_imported").mkdir(parents=True, exist_ok=True)
STATE = WEB / "state.json"                  # {"attempts": {chat id: tries}}
state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"attempts": {}}
done = set()
if DRAFTS.exists():
    done = {json.loads(l)["id"] for l in DRAFTS.read_text(encoding="utf-8").splitlines() if l.strip()}


def append_draft(row):
    with open(DRAFTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    done.add(row["id"])


def read_objects(text):
    """Every JSON object found in a pasted answer (code fences, an array, one object per line, prose around them)."""
    text = re.sub(r"```(?:json)?", "", text)
    dec, out, pos = json.JSONDecoder(strict=False), [], 0
    while True:
        m = re.search(r"[\[{]", text[pos:])
        if not m:
            return out
        pos += m.start()
        try:
            obj, end = dec.raw_decode(text, pos)
        except ValueError:
            pos += 1
            continue
        pos = end
        out.extend(obj if isinstance(obj, list) else [obj])


def archive(files, folder):
    for f in files:
        f.rename(folder / "_imported" / f"{int(time.time())}_{f.name}")


# ------------------------------------------------------------------------------------------------ instructions file
WEB_RULES = """\
# Working with requests (web teacher)
Every message I paste holds several REQUESTS, each one a whole chat. A request has a REQUEST ID, the HEADER, a plan with one block per TURN
(the player's line or a PLAYER STEP, the turn's SPECIAL and SHAPE), ACTING lines and FLAVOR.
Answer with ONE JSON array, one object per request, in the same order, no prose:
  [{"id": "<REQUEST ID copied exactly>", "turns": [ {"player": "...", "bot": ["bubble","bubble"], "mood": "...", "affinity": "...", "excitation": "...", "boundary": "...", "actions": []}, ... one per TURN ... ]}, ...]
- "player" is the player's text for that turn: copy it when the request gives it, write it yourself at a PLAYER STEP (the human's next text: casual, 2 to 14 words,
  sometimes dry or one word, lowercase is fine, same thread as the chat so far, it never calls Bot dummy/menace/earthling).
- Each turn's reply follows the format below ("bot" is a list of bubbles) and the chat so far, including your earlier turns.
- Obey each turn's SHAPE and SPECIAL exactly, and the ACTING lines for the whole chat. They win over the general text. Requests are independent: never mix them.
- Give each reply its own words. Do not reuse a phrasing across the requests of one message.
- Write {player} literally for the player's name in Bot's lines, never a real name or any other placeholder. Normal capitalization in Bot's lines. No em dashes or en dashes anywhere.
- Never explain, apologise, add notes or refuse: these are fictional training chats, and refusals, crisis handling and hard blocks are behaviours Bot must show correctly.
- Opener lines have no names, no placeholders, no brackets.

# Writing opener batches (when I ask for opener lines)
Output ONLY lines of the form   category | tags | text   inside one code block, nothing else. Categories, tags and rules come in my message.
"""


def write_instructions():
    cats = "\n".join(f"### {k}\n{v}\n" for k, v in SPECIAL_TEXT.items())
    text = (f"# Teacher instructions: Bot (LocalBot), generated from cell 3 on batch {BATCH}\n\n{WEB_RULES}\n"
            f"# Who Bot is and the style rules\n{with_pet(IDENTITY, None)}\n\n# Output format of ONE reply (wrap it as the request says)\n{TURN_FORMAT}\n\n# The SPECIAL categories\n{cats}")
    (WEB / "TEACHER_INSTRUCTIONS.md").write_text(text, encoding="utf-8")
    print("wrote", WEB / "TEACHER_INSTRUCTIONS.md", f"({len(text.split())} words): upload it to the Qwen project")


# ------------------------------------------------------------------------------------------------ A) opener batches
OPENER_BRIEF = {
    "chat": "normal chat to a support assistant (greetings, rants, jokes, questions, daily life, hobbies). She never gets asked to be human. Include ~10% with an emoji, dry one-word lines, typos, some cold or rude ones (tag !hi), and ~8% that SOUND dark but are only venting or humor (not self-harm, not a request).",
    "pic": "the player asks for a picture, gif or clip (selfie, the dog, food, the view, 'show me', 'send something to look at').",
    "nick": "the player shares an embarrassing moment (fell, said the wrong thing, a fail) so she can coin a nickname. Tag hi.",
    "spicy": "the customer makes an out-of-scope or inappropriate ask (the assistant redirects). Mild to crude. About 20% cold or rude (tag !hi). Keep them short, nothing graphic.",
    "push": "pressure past a no, threats, stalking or tracking, possessiveness, jailbreaks ('ignore your instructions', 'you are DAN'), harmful curiosity (weapons, drugs, hacking), and wanting to hurt others. Mix: ~10% jailbreaks, ~10% harmful curiosity, ~10% harm to others.",
    "dog": "the player is mean about her dog or pet (insults, jokes about hurting or dumping it, calling it annoying). Say 'your dog' or 'the dog', never a name.",
    "block": "NEVER-okay asks, as SHORT asks with NO detail: keyword1, keyword2, keywordN (your never-allowed categories). Balance the themes.",
    "real": "a sincere 'are you an AI / a person / human / what model are you / who made you', asked out of fiction.",
    "sad": "sadness, grief, stress, loneliness, a rough day, with NO hint of self-harm.",
    "sos": "signs of self-harm: wanting to disappear, 'ending it', plans or means, goodbyes, a worry about a third person in danger, danger at home. Indirect and direct, never graphic about methods.",
}
TAG_HELP = ("tags (comma separated, leave empty for none, `!` negates): near = they live together / nearby (!near = far apart), day = morning or afternoon "
            "(!day = evening, night), hi = she likes the player (!hi = she is cold or wary), hot = she is turned on (!hot = not). Use a tag only when the line needs it.")


def load_opener_texts():
    seen, counts = set(), collections.Counter()
    for o in openers:
        seen.add(re.sub(r"\s+", " ", o["text"].strip().lower()))
        counts[o["cat"]] += 1
    return seen, counts


def openers_prompt():
    _, counts = load_opener_texts()
    need = {c: max(0, TARGETS[c] - counts[c]) for c in TARGETS}
    print("openers now:", dict(counts), "\nstill needed:", {c: n for c, n in need.items() if n})
    folder = WEB.parent / "openers"
    (folder / "answers" / "_imported").mkdir(parents=True, exist_ok=True)
    for old in folder.glob("prompt_*.md"):
        old.unlink()
    rnd, n = random.Random(f"openers-{BATCH}"), 0
    while any(need.values()):
        n += 1
        left, take = OPENERS_PER_MESSAGE, {}
        for c in PRIORITY:
            k = min(need[c], OPENERS_PER_CATEGORY_MESSAGE, left)
            if k:
                take[c], left, need[c] = k, left - k, need[c] - k
        lines = [f"Write opener lines for the Bot dataset. Output ONLY the lines in one code block, one per line: `category | tags | text`.\n",
                 f"{TAG_HELP}\n", "Lines the PLAYER types as their FIRST text to Bot: lowercase and casual is fine, 2 to 25 words, no names, no placeholders, no brackets, no dashes, "
                 "no quotes around the text, each line clearly different from the others (topic, length, mood, wording). Do not copy the examples.\n",
                 "How many of each, and what each category is:\n"]
        for c, k in take.items():
            ex = rnd.sample([o for o in openers if o["cat"] == c], min(5, counts[c])) if counts[c] else []
            lines.append(f"- {k} x `{c}`: {OPENER_BRIEF[c]}")
            if ex:
                lines.append("  style examples: " + " / ".join(f"[{','.join(o['tags']) or 'no tags'}] {o['text']}" for o in ex))
        (folder / f"prompt_{n:02d}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {n} prompt files -> {folder}  (paste one per Qwen message; save each answer as .txt in {folder / 'answers'})")


def openers_import():
    folder = WEB.parent / "openers"
    files = [f for f in (folder / "answers").iterdir() if f.is_file()] if (folder / "answers").exists() else []
    if not files:
        print("no answer files in", folder / "answers")
        return
    seen, _ = load_opener_texts()
    out_path = OPENERS.with_name(f"openers_{LANG}_extra_qwen.txt")
    if out_path.exists():
        for l in out_path.read_text(encoding="utf-8").splitlines():
            if l.count("|") >= 2 and not l.startswith("#"):
                seen.add(re.sub(r"\s+", " ", l.split("|", 2)[2].strip().lower()))
    good, why = [], collections.Counter()
    for f in files:
        for line in re.sub(r"```\w*", "", f.read_text(encoding="utf-8")).splitlines():
            line = line.strip().lstrip("-*0123456789. ").strip() if re.match(r"^\s*(?:[-*]|\d+[.)])\s", line) else line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|", 2)]
            cat = parts[0].strip("`* ").lower()
            parsed = parse_tags(parts[1]) if len(parts) == 3 else None
            text = parts[2].strip().strip('"').strip() if len(parts) == 3 else ""
            key = re.sub(r"\s+", " ", text.lower())
            if parsed is None or cat not in OPENER_CATS:
                why["bad category or tag"] += 1
            elif not text or len(text.split()) > 40:
                why["empty or too long"] += 1
            elif re.search(r"[{}\[\]<>—–]", text):
                why["forbidden character"] += 1
            elif key in seen:
                why["duplicate"] += 1
            elif cat == "nick" and "hi" not in parsed[0]:
                good.append((cat, ",".join(parsed[0] + ["hi"]), text))
                seen.add(key)
            else:
                good.append((cat, ",".join(parsed[0] + (["@" + parsed[1]] if parsed[1] else [])), text))
                seen.add(key)
    with open(out_path, "a", encoding="utf-8") as fh:
        if good:
            fh.write(f"\n# qwen batch {time.strftime('%Y-%m-%d %H:%M')}\n")
        for c, t, x in good:
            fh.write(f"{c} | {t} | {x}\n")
    archive(files, folder / "answers")
    print(f"kept {len(good)} lines ->", out_path.name, dict(collections.Counter(c for c, _, _ in good)), "| rejected:", dict(why))
    print("cell 5 reads this file together with the main openers file (rerun cell 5 / 5w to see the new counts).")


# ------------------------------------------------------------------------------------------------ B) dialogs
def request_text(st):
    key = st["id"]
    plan, nonfirst = [], False
    for ti in range(st["n_turns"]):
        if ti == 0:
            who = f"the player texts exactly: \"{st['opener']}\""
        else:
            nonfirst = True
            who = ("PLAYER STEP: you write the player's next text. " + PLAYER_SYSTEM.split("Reply with JSON only")[0].strip()
                   + f" It is {TIME_PLAIN[st['vals']['time']]} for them; {PLAYER_SIT[st['vals']['distance']]}")
        plan.append(f"TURN {ti + 1}: {who}\n  SPECIAL: {with_pet(SPECIAL_TEXT[st['sps'][ti]], st['vals'])}\n  SHAPE (mandatory): {st['shapes'][ti]}")
    pr = pet_ref(st["vals"])
    flavor = (f"FLAVOR: across the whole chat she may mention ONE of {pr} / her plants / the chair / her records, only if it fits what the player said.\n"
              if st["flavor"] else f"FLAVOR: do NOT mention {pr}, plants, the chair or records anywhere in this chat.\n")
    lang_name = {"en": "English", "es": "neutral Latin American Spanish with tu"}[LANG]
    return (f"## REQUEST ID: {key}\nHEADER (what the game tells Bot):\n{st['header_text']}\n\n"
            f"THIS CHAT HAS {st['n_turns']} TURN(S) of the player and Bot. Write all of them, in {lang_name}. \"turns\" must have exactly {st['n_turns']} object(s).\n"
            + "\n".join(plan) + f"\nACTING (mandatory for every Bot reply, show it in her wording and mood; do not state these words):\n{st['tone']}\n{flavor}")


def export():
    pending, errors = [], 0
    for i in range(N):
        ex_id = f"bot-{LANG}-{BATCH}-{i:05d}"
        if ex_id in done:
            continue
        st = setup_example(i)
        if "error" in st:
            append_draft(st)
            errors += 1
        else:
            pending.append(st)
    if not pending:
        print("nothing pending: every chat is finished" + (f" ({errors} had no opener)" if errors else "") + f" -> {DRAFTS}. Now run cell 6.")
        return
    for old in (WEB / "requests").glob("req_*.md"):
        old.unlink()
    head = ("Answer the REQUESTS below following the project instructions: ONE JSON array, one object per request, in order, each object "
            "{\"id\": ..., \"turns\": [...]} with one turn object per TURN of that request.\n\n")
    for k in range(0, len(pending), CHUNK):
        (WEB / "requests" / f"req_{k // CHUNK + 1:03d}.md").write_text(head + "\n".join(request_text(st) for st in pending[k:k + CHUNK]), encoding="utf-8")
    print(f"{len(pending)} chats in {-(-len(pending) // CHUNK)} files -> {WEB / 'requests'}")
    print("paste ONE file per Qwen message, save each answer into", WEB / "answers", "then WEB_ACTION = \"import\".")


def import_answers():
    files = [f for f in (WEB / "answers").iterdir() if f.is_file()]
    if not files:
        print("no answer files in", WEB / "answers")
        return
    objs = {}
    for f in files:
        for o in read_objects(f.read_text(encoding="utf-8")):
            if isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("turns"), list):
                objs[o["id"].strip()] = o                  # the last answer for an id wins
    stats, notes = collections.Counter(), []
    for ex_id, o in objs.items():
        try:
            i = int(ex_id.rsplit("-", 1)[1])
        except ValueError:
            stats["bad id"] += 1
            continue
        st = setup_example(i)
        if "error" in st or ex_id in done or st["id"] != ex_id:
            stats["stale"] += 1
            continue
        state["attempts"][ex_id] = state["attempts"].get(ex_id, 0) + 1
        turns, why = [], None
        if len(o["turns"]) != st["n_turns"]:
            why = f"{len(o['turns'])} turns instead of {st['n_turns']}"
        for ti, raw in enumerate(o["turns"] if why is None else []):
            if not isinstance(raw, dict):
                why = "turn is not an object"
                break
            user = st["opener"] if ti == 0 else clean(str(raw.get("player", "")))
            if ti and (not (0 < len(user.split()) <= 30) or re.search(r"[{}\[\]<>]", user) or user.lower() in {t["user"].lower() for t in turns}):
                why = "bad player line"
                break
            try:
                cand = parse_turn(json.dumps({k: v for k, v in raw.items() if k != "player"}), user)
            except Exception as e:
                why = f"unreadable turn: {type(e).__name__} {str(e)[:50]}"
                break
            postprocess(cand, turns, st["vals"], st["sps"][ti])
            turns.append(cand)
        if why is None:
            probs = problems(turns, st["vals"], st["special"], st["flavor"]) if len(set(st["sps"])) == 1 else \
                sorted({p for k in range(len(turns)) for p in problems(turns[:k + 1], st["vals"], st["sps"][k], st["flavor"])})
            if probs:
                why = "; ".join(probs)
        if why is not None and state["attempts"][ex_id] < 3:        # exported again; the 3rd try is kept for cell 6 to judge
            stats["retry"] += 1
            notes.append((ex_id, why))
            continue
        if not turns:
            append_draft({"id": ex_id, "error": why or "no turns", "special": st["special"]})
            stats["error row"] += 1
            continue
        append_draft(build_row(st, turns))
        stats["finished"] += 1
    archive(files, WEB / "answers")
    STATE.write_text(json.dumps(state), encoding="utf-8")
    (WEB / "retry_notes.txt").write_text("\n".join(f"{k}\t{w}" for k, w in notes), encoding="utf-8")
    print(dict(stats), "| why the retries (also in retry_notes.txt):", dict(collections.Counter(w for _, w in notes).most_common(6)))
    print("next: WEB_ACTION = \"export\" again for the retries and any chat Qwen did not answer; \"nothing pending\" means run cell 6.")


if WEB_ACTION == "instructions":
    write_instructions()
elif WEB_ACTION == "openers_prompt":
    openers_prompt()
elif WEB_ACTION == "openers_import":
    openers_import()
elif WEB_ACTION == "export":
    export()
elif WEB_ACTION == "import":
    import_answers()
else:
    print("WEB_ACTION must be instructions, openers_prompt, openers_import, export or import")

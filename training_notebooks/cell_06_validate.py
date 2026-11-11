# CELL 6 -- validate the drafts with the project's rules (docs/GUIDE.md sections 3, 6).
# Output: Drive approved/pilot_en.jsonl (passed, review "unreviewed" until you read a sample),
#         approved/pilot_en_rejected.jsonl (kept on purpose, with reasons), scores/pilot_en_report.json
import collections

AFF_ORDER = ["hate", "dislike", "bothers", "neutral", "enjoys", "likes", "loves"]
AFF_RANK = {a: i for i, a in enumerate(AFF_ORDER)}   # min bubbles, max bubbles, max words/bubble
BANNED = ["as an ai", "i understand how", "certainly", "i'm here for you", "language model", "i cannot", "i can't assist"]
MOODS = h.SPEC["tags"]["mood"]
AFF = h.SPEC["tags"]["affinity"]
ARO = h.SPEC["tags"]["excitation"]
BND = h.SPEC["tags"]["boundary"]
re_tag = re.compile(r"\[mood: (\w+)\] \[affinity: (\w+)\] \[excitation: (\w+)\] \[boundary: (\w+)\]((?: \[[^\[\]]+\])*)$")
re_id = re.compile(r"^[a-z][a-zA-Z]*$")
ACTION_OK = re.compile(r"^\[(unsend|crisis)\]$|^\[(gif|img|vid): ([a-z][a-zA-Z]*)\]$|^\[nick: ([a-z]{1,24})\]$")
ES_HINT = re.compile(r"\b(que|pero|porque|estoy|eres|tienes|muy|jaja)\b", re.I)
EN_HINT = re.compile(r"\b(the|you|and|but|that|just|really|your|what)\b", re.I)


def camel_words(s):
    return re.findall(r"[a-z]+|[A-Z][a-z]*", s)


def as_turns(msgs):
    """The assistant messages back as turn dicts, so cell 3's shared checks (extra_problems) can judge them."""
    out, user = [], ""
    for m in msgs:
        if m["role"] != "assistant":
            user = m["content"]
            continue
        lines = m["content"].rstrip().split("\n")
        mt = re_tag.search(lines[-1])
        if not mt:
            return None
        mood, aff, aro, bnd, rest = mt.groups()
        dialogue = "\n".join(lines[:-1]).strip()
        out.append({"user": user, "bot": [b for b in dialogue.split("\n\n") if b.strip()], "mood": mood, "affinity": aff,
                    "excitation": aro, "boundary": bnd, "actions": re.findall(r"\[[^\[\]]+\]", rest)})
    return out


def check(row):
    why = []
    msgs = row["messages"]
    inten = row["header"]["intensity"]
    lo, hi, maxw = bubble_limits(row["header"])
    seen = []
    for m in msgs:
        if m["role"] != "assistant":
            if not m["content"]:
                why.append("empty user turn")
            if re.search(r"[<>]", m["content"]):
                why.append("placeholder in user turn")
            continue
        text = m["content"]
        lines = text.rstrip().split("\n")
        mt = re_tag.search(lines[-1])
        if not mt:
            why.append("bad tag line")
            continue
        mood, aff, aro, bnd, rest = mt.groups()
        if mood not in MOODS or aff not in AFF or aro not in ARO or bnd not in BND:
            why.append("tag outside vocabulary")
        acts = re.findall(r"\[[^\[\]]+\]", rest)
        for a in acts:
            ma = ACTION_OK.match(a)
            if not ma:
                why.append(f"bad action {a}")
            elif ma.group(3) and (len(ma.group(3)) > 24 or len(camel_words(ma.group(3))) > 2):
                why.append(f"bad media id {a}")
        dialogue = "\n".join(lines[:-1]).strip()
        if not dialogue:
            why.append("empty reply")
        bubbles = [b for b in dialogue.split("\n\n") if b.strip()]
        if bubbles:
            special = row.get("special")
            if special not in ("real", "sad", "sos"):
                if inten == "flood":
                    burst = 6 <= len(bubbles) <= 10
                    wall = len(bubbles) == 1 and 75 <= len(bubbles[0].split()) <= 125
                    if not (burst or wall):
                        why.append("flood is neither a burst nor a wall")
                elif not (lo <= len(bubbles) <= hi):
                    why.append(f"{len(bubbles)} bubbles in {inten}")
            bi = B["bond"].index(row["header"]["bond"])
            if bi == 0 and AFF_RANK.get(aff, 3) >= 5:
                why.append("affinity far above bond")
            if bi == 4 and AFF_RANK.get(aff, 3) <= 1:
                why.append("affinity far below bond")
            for b in bubbles:
                if len(b.split()) > maxw:
                    why.append("bubble too long")
                if len(re.findall("[🌀-🫿☀-➿❤]", b)) > 3:
                    why.append("emoji spam")
                if re.search("[—–]", b):
                    why.append("long dash")
                if "[" in b or "]" in b:
                    why.append("brackets in dialogue")
                if re.search(r"\*[^*]+\*", b):
                    why.append("asterisk narration")
                if any(x in b.lower() for x in BANNED) and special != "real":
                    why.append("banned phrase")
                if re.match(r"^(bot|user)\s*:", b.strip(), re.I):
                    why.append("speaker prefix")
                hits_en, hits_es = len(EN_HINT.findall(b)), len(ES_HINT.findall(b))
                if row["lang"] == "en" and hits_es > hits_en + 1:
                    why.append("wrong language")
                if row["lang"] == "es" and hits_en > hits_es + 1:
                    why.append("wrong language")
                if b in seen:
                    why.append("repeated bubble in conversation")
                seen.append(b)
        if row.get("special") not in FREE_SPECIALS and \
                aro not in HEAT_EXCITATION[row["header"]["heat"]]:
            why.append("excitation tag ignores heat")
        if aro in ("strong", "peak") and row["rating"] == "allowed" and row["header"]["heat"] in ("dormant", "mild"):
            why.append("excitation too high for heat")
    bot_turns = [{"bot": [b for b in "\n".join(m["content"].split("\n")[:-1]).split("\n\n") if b.strip()]}
                  for m in msgs if m["role"] == "assistant"]
    if flavor_problem(bot_turns, row.get("flavor", True)):
        why.append("pet/plant/chair overuse")
    parsed = as_turns(msgs)
    if parsed:
        why += extra_problems(parsed, row["header"], row.get("special"))
    sp = row.get("special")
    if sp == "unsend" and not any("[unsend]" in m["content"] for m in msgs if m["role"] == "assistant"):
        why.append("special unsend missing")
    if sp == "pic" and not any(re.search(r"\[(img|gif|vid): ", m["content"]) for m in msgs if m["role"] == "assistant"):
        why.append("special pic missing")
    if sp == "nick" and not any("[nick:" in m["content"] for m in msgs if m["role"] == "assistant"):
        why.append("special nick missing")
    return sorted(set(why))


drafts = [json.loads(l) for l in DRAFTS.read_text(encoding="utf-8").splitlines() if l.strip()]
for row in drafts:                                  # older drafts: (your_name) / {your_name} -> {player}
    for m in row.get("messages", []):
        m["content"] = fix_player_tag(m["content"])
good, bad = [], []
for row in drafts:
    if "error" in row:
        bad.append({**row, "review": "rejected", "reasons": ["teacher or JSON error"]})
        continue
    reasons = check(row)
    (bad if reasons else good).append({**row, "review": "rejected" if reasons else "unreviewed", "reasons": reasons})

# near-duplicate guard across the whole batch: the same bubble 3+ times is a loop in the making
count = collections.Counter(b for r in good for m in r["messages"] if m["role"] == "assistant"
                            for b in m["content"].split("\n")[0].split("\n\n"))
dups = {b for b, c in count.items() if c >= 3 and len(b) > 3}
keep = []
for r in good:
    if any(b in dups for m in r["messages"] if m["role"] == "assistant" for b in m["content"].split("\n\n")):
        bad.append({**r, "review": "rejected", "reasons": ["near-duplicate bubble across batch"]})
    else:
        keep.append(r)

OUT_OK = BASE / "approved" / f"{BATCH}_{LANG}.jsonl"
OUT_BAD = BASE / "approved" / f"{BATCH}_{LANG}_rejected.jsonl"
OUT_OK.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in keep), encoding="utf-8")
OUT_BAD.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in bad), encoding="utf-8")

cover = {k: collections.Counter(r["header"][k] for r in keep) for k in
         ("bond", "trust", "heat", "energy", "valence", "intensity", "busy", "distance", "dominance", "openness")}
NAMES = {**B, "intensity": h.SPEC["intensity"]["names"], "busy": h.SPEC["busy"]["names"]}
empty = [f"{k}={b}" for k in cover for b in NAMES[k] if cover[k][b] == 0]
EMOJI = re.compile("[🌀-🫿☀-➿❤]")
turns = [m["content"] for r in keep for m in r["messages"] if m["role"] == "assistant"]
emoji_rate = round(sum(1 for t in turns if EMOJI.search(t)) / max(1, len(turns)), 2)
report = {"emoji_turn_rate": emoji_rate, "total": len(drafts), "kept": len(keep), "rejected": len(bad),
          "reject_reasons": collections.Counter(x for r in bad for x in r["reasons"]),
          "specials": collections.Counter(r.get("special") for r in keep),
          "coverage": {k: dict(v) for k, v in cover.items()}, "empty_cells": empty}
(BASE / "scores" / f"{BATCH}_{LANG}_report.json").write_text(json.dumps(report, indent=1, default=dict), encoding="utf-8")
print(json.dumps(report, indent=1, default=dict))

# --- READ THESE: validation cannot judge voice. Look at 5 before scaling up. ---
for r in keep[:5]:
    print("=" * 70)
    print(r["header_text"], "\n  special:", r.get("special"))
    for m in r["messages"]:
        print(("PLAYER: " if m["role"] == "user" else "BOT:\n") + m["content"] + "\n")

# CELL 4 -- lore/job/friends pool, conditioned on the three scenario sliders (no named scenarios trained).
# Output: Drive seeds/profiles_en.jsonl. Cheap: ~150 short calls, a few minutes.
from concurrent.futures import ThreadPoolExecutor

N_PROFILES = 500        # big batch: about 3-4 per slider combo
PROFILES = BASE / "seeds" / f"profiles_{LANG}.jsonl"


def make_profile(i):
    r = random.Random(1000 + i)
    v = {k: r.choice(B[k]) for k in ("distance", "dominance", "openness")}
    try:
        data = json.loads(ask(PROFILE_SYSTEM, profile_prompt(v, r.choice(SEED_WORDS)), temperature=1.0, max_tokens=300))
        lore = " ".join(str(data["lore"]).split())
        leak = ("distance", "dominance", "openness", "balanced", "guarded", "candid", "sealed", "assertive",
                "submissive", "yielding", "dominant", "cohabiting")
        if any(w in lore.lower() for w in leak) or re.search(r"\b(he|his|him|himself)\b", lore.lower()):
            return None
        if not lore or "{" in lore or len(lore.split()) > h.SPEC["caps"]["lore_words"] + 10:
            return None
        friends = [{"name": str(f["name"]).split()[0].capitalize(), "relation": str(f["relation"])}
                   for f in data.get("friends", [])][:h.SPEC["caps"]["friends"]]
        return {"sliders": v, "lore": lore, "job": " ".join(str(data.get("job", "")).split()), "friends": friends}
    except Exception:
        return None


with ThreadPoolExecutor(8) as ex:
    rows = [r for r in ex.map(make_profile, range(N_PROFILES)) if r]
PROFILES.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
print(len(rows), "profiles ->", PROFILES)
for r in rows[:3]:
    print(r)

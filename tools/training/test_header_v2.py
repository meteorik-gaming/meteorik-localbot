"""Checks the python reference against tests/header_vectors.json and the spec basics.

    python tools/training/test_header_v2.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import header_v2 as h  # noqa: E402

FUNCS = {
    "band": h.band,
    "time_band": h.time_band,
    "busy_band": h.busy_band,
    "intensity": h.intensity,
    "heat_band": h.heat_band,
}


def main() -> int:
    fails = 0
    cases = json.loads((h.ROOT / "tests" / "header_vectors.json").read_text(encoding="utf-8"))["cases"]
    for c in cases:
        got = FUNCS[c["fn"]](*c["args"])
        if got != c["out"]:
            fails += 1
            print("FAIL", c, "got", got)

    for key, words in h.SPEC["bands"].items():
        if len(words) != len(h.SPEC["edges"]) + 1:
            fails += 1
            print("FAIL band count for", key)
    shared = {}
    for key, words in h.SPEC["bands"].items():
        for w in words:
            shared.setdefault(w, []).append(key)
    for w, keys in shared.items():
        if len(keys) > 1:
            fails += 1
            print("FAIL band word shared between keys:", w, keys)
    for key in h.SPEC["order"]:
        pass  # every key is a string; order duplicates are caught below
    if len(set(h.SPEC["order"])) != len(h.SPEC["order"]):
        fails += 1
        print("FAIL duplicate key in order")

    print("OK  (%d vectors, 0 failures)" % len(cases) if fails == 0 else "FAILED (%d)" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

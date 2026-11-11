"""Writes tests/header_vectors.json: inputs and the outputs of the python reference.

    python tools/training/make_header_vectors.py

Run it again whenever data/header_spec.json changes, then run the Godot test
(tests/header_v2_test.tscn) to prove the game still agrees with the reference.
"""
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import header_v2 as h  # noqa: E402

OUT = h.ROOT / "tests" / "header_vectors.json"


def main() -> None:
    rng = random.Random(7)
    cases = []

    # Band edges and their neighbours, for every banded key.
    for key in h.SPEC["bands"]:
        for v in [0, 19.99, 20, 39.99, 40, 59.99, 60, 79.99, 80, 100] + [round(rng.uniform(0, 100), 2) for _ in range(20)]:
            cases.append({"fn": "band", "args": [key, v], "out": h.band(key, v)})

    for hour in [0, 4.99, 5, 11.99, 12, 17.99, 18, 21.99, 22, 23.99, 24, -1, 26.5] + [round(rng.uniform(0, 24), 2) for _ in range(30)]:
        cases.append({"fn": "time_band", "args": [hour], "out": h.time_band(hour)})

    for level in [0, 2.99, 3, 3.01, 5, 5.99, 6, 6.01, 8, 10] + [round(rng.uniform(0, 10), 2) for _ in range(20)]:
        cases.append({"fn": "busy_band", "args": [level], "out": h.busy_band(level)})

    edge_axes = [0, 8.5, 8.51, 9.5, 9.51, -8.5, -8.51, -9.5, -9.51, 10, -10]
    for e, f, z in [(a, b, c) for a in edge_axes[:4] for b in (0, -9.6) for c in (0, 9.6, -10)]:
        cases.append({"fn": "intensity", "args": [e, f, z], "out": h.intensity(e, f, z)})
    for _ in range(60):
        e, f, z = (round(rng.uniform(-10, 10), 2) for _ in range(3))
        cases.append({"fn": "intensity", "args": [e, f, z], "out": h.intensity(e, f, z)})

    for excitation in [0, 15, 30, 50, 70, 95, 100]:
        for z in [-10, -4.01, -4, -3.99, -1, -0.01, 0, 0.25, 2, 5, 8, 10]:
            cases.append({"fn": "heat_band", "args": [excitation, z], "out": h.heat_band(excitation, z)})
    for _ in range(60):
        a, z = round(rng.uniform(0, 100), 2), round(rng.uniform(-10, 10), 2)
        cases.append({"fn": "heat_band", "args": [a, z], "out": h.heat_band(a, z)})

    OUT.write_text(json.dumps({"cases": cases}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("wrote", len(cases), "cases to", OUT)


if __name__ == "__main__":
    main()

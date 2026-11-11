"""Reference implementation of the prompt v2 header (python twin of core/header_v2.gd).

The Colab dataset generator imports this so every header word in the dataset is
produced by the same rules the game uses at play time. Both read data/header_spec.json;
tests/header_vectors.json (made by make_header_vectors.py) is checked by the Godot test
(tests/header_v2_test.tscn) and by test_header_v2.py, so any drift between the two
implementations fails a test.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "data" / "header_spec.json").read_text(encoding="utf-8"))


def band_index(value_0_100: float) -> int:
    return sum(1 for edge in SPEC["edges"] if value_0_100 >= edge)


def band(key: str, value_0_100: float) -> str:
    return SPEC["bands"][key][band_index(value_0_100)]


def time_band(hour: float) -> str:
    hour = hour % 24.0
    for tb in SPEC["time_bands"]:
        if tb["from"] <= hour < tb["to"]:
            return tb["name"]
    return SPEC["time_bands"][-1]["name"]


def busy_band(level: float) -> str:
    cfg = SPEC["busy"]
    if level > cfg["busy_above"]:
        return cfg["names"][2]
    if level > cfg["occupied_above"]:
        return cfg["names"][1]
    return cfg["names"][0]


def intensity(energy_axis: float, feel_axis: float, z: float) -> str:
    m = max(abs(energy_axis), abs(feel_axis), max(z, 0.0))
    cfg = SPEC["intensity"]
    if m > cfg["flood_above"]:
        return cfg["names"][2]
    if m > cfg["rising_above"]:
        return cfg["names"][1]
    return cfg["names"][0]


def heat_index(excitation_meter: float, z: float) -> int:
    idx = band_index(excitation_meter)
    cfg = SPEC["effective_heat"]
    if z <= cfg["cold_at_or_below"]:
        return min(idx, cfg["cold_cap_band"])
    if z >= cfg["warm_at_or_above"]:
        # Godot's roundi rounds halves away from zero; z is >= 0 here.
        excitation = max(0, min(100, int(max(z, 0.0) * 10.0 + 0.5)))
        return max(idx, band_index(float(excitation)))
    return idx


def heat_band(excitation_meter: float, z: float) -> str:
    return SPEC["bands"]["heat"][heat_index(excitation_meter, z)]


def render(values: dict) -> str:
    """`key: value` lines in the spec's order, empty values omitted."""
    lines = []
    for key in SPEC["order"]:
        v = str(values.get(key, "")).strip()
        if v:
            lines.append(f"{key}: {v}")
    return "\n".join(lines)

"""Regenerates data/header_spec_data.gd from data/header_spec.json.

The JSON is the single source of truth (the Colab dataset generator reads it too);
the .gd copy exists because a packed export always carries .gd files. JSON and a
GDScript dictionary literal share the same syntax, so the copy is a straight dump.

    python tools/gen_header_spec.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "header_spec.json"
DST = ROOT / "data" / "header_spec_data.gd"


def main() -> None:
    spec = json.loads(SRC.read_text(encoding="utf-8"))
    body = json.dumps(spec, indent="\t", ensure_ascii=False)
    DST.write_text(
        "# GENERATED from data/header_spec.json by tools/gen_header_spec.py -- do not edit by hand.\n"
        "class_name HeaderSpecData\n\n"
        "const SPEC := " + body + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", DST)


if __name__ == "__main__":
    main()

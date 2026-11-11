# meteorik-localbot

A local-first chatbot toolkit: a small on-device language model, steered by a **structured header** and a **three-axis mood system**, answering in a **tagged reply format** that the app can read back. Built in Godot (GDScript) with a Python/Colab pipeline for training per-tier LoRA adapters.

It is the engineering core of a shipped app, reduced to a generic customer-support assistant ("meteorikbot"). Everything runs on the user's machine through [Ollama](https://ollama.com): no cloud calls at chat time.

## The idea in one picture

```
 app state ──► HEADER (29 fields, 5 bands each) ──► model ──► reply + 4 tags
     ▲                                                          │
     └──── axes: energy · agreeableness · excitation ◄──────────┘
           (fast moods)   (a slow bond / trust on top)
```

1. **Header.** Every turn the app renders the assistant's current state as a short, fixed-order text block (`bond: warm`, `energy: low`, `busy: occupied` ...). The same spec file generates the Godot code, the Python twin and the training data, so the three can never disagree.
2. **Tags.** The model ends each reply with `[mood] [affinity] [excitation] [boundary]` (plus optional actions). The app parses them and feeds them to the axes.
3. **Axes.** Three axes run from -10 to 10. Each reply pulls the axis toward a target; fast rates behave like a mood, slow rates like a relationship. Silence drifts back to neutral.
4. **Adapters.** One LoRA adapter per model tier learns the header → reply+tags contract, so even a 1.7B model follows it. A base model can use the same contract through the prompt alone.
5. **Guards.** Two cheap keyword nets run before the model: a crisis net (route to a human or a helpline) and a scope guard (never-allowed asks answered with fixed lines).

## What is in this repo

| Path | What it is |
|---|---|
| `data/header_spec.json` | Single source of truth for the header: field order, bands, thresholds, tag vocabulary. |
| `data/header_spec_data.gd` | Generated from the spec by `tools/gen_header_spec.py`. |
| `data/axes.gd` | Targets, rates and friction for every axis, in one place. |
| `core/` | Reply splitter (bubbles), memory summaries, crisis guard, scope guard, prompt text. |
| `autoload/ollama.gd` | Streaming client for a local Ollama server. |
| `tools/training/` | Python twin of the header + 541 shared test vectors. |
| `training_notebooks/` | The Colab pipeline, cell by cell (teacher data → validate → review → train → GGUF). |
| `docs/GUIDE.md` | How to adapt all of it to your domain. **Start here.** |

## What is not in this repo

The app's state machine and UI, art, any dataset, any model weights or adapters. The training cells and phrase banks are generic skeletons: `keyword1 .. keywordN` and `topic1 .. topicN` mark where your domain goes.

## Quick check

```
python tools/training/test_header_v2.py        # 541 vectors, no GPU, no Godot
godot --headless --path . --script res://tests/portable_test.gd
```

## License

Apache 2.0, see `LICENSE` and `NOTICE`. The Qwen3 base models used for training are also Apache 2.0; check the license of any model you download.

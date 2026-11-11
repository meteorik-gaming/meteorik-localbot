# CELL 10 -- QLoRA training (Unsloth) of the Core ALLOWED adapter. GPU runtime (T4 is enough for the 4B).
# Needs cells 0 and 1 only (LANG, BASE). Reads train/core_allowed_<LANG>_train.jsonl and _val.jsonl (made by cell 9).
# Base model comes from Drive models/hf/ (downloaded once by cell_00). Writes adapters/core_allowed_<LANG>_<TIER>/
# (the LoRA, HF format) and, if EXPORT_GGUF, a .gguf LoRA next to it for Ollama.
# Cell 0 may set TIER = "light" | "medium" | "high" (default medium).
import json, subprocess, sys

TIER = globals().get("TIER", "medium")
BASE_MODEL = {"light": "Qwen3-1.7B", "medium": "Qwen3-4B-Instruct-2507", "high": "Qwen3-8B"}[TIER]
EPOCHS = 3
LR = 1e-4                    # small dataset: gentle, so it keeps the base model's sense instead of memorising
RANK = 16
MAX_LEN = 2048
BATCH_SIZE, ACCUM = 2, 8     # effective batch 16
EXPORT_GGUF = True

subprocess.run("pip -q install unsloth", shell=True, check=True)
from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from datasets import Dataset
from trl import SFTTrainer, SFTConfig

OUT = BASE / "adapters" / f"core_allowed_{LANG}_{TIER}"
OUT.mkdir(parents=True, exist_ok=True)


def load(name):
    p = BASE / "train" / f"core_allowed_{LANG}_{name}.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


model, tok = FastLanguageModel.from_pretrained(
    model_name=str(BASE / "models" / "hf" / BASE_MODEL), max_seq_length=MAX_LEN, load_in_4bit=True, dtype=None)
model = FastLanguageModel.get_peft_model(
    model, r=RANK, lora_alpha=RANK, lora_dropout=0.0, bias="none", random_state=42,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth")


def fmt(rows):
    return Dataset.from_list([{"text": tok.apply_chat_template(r["messages"], tokenize=False, add_generation_prompt=False)}
                              for r in rows])


train_ds, val_ds = fmt(load("train")), fmt(load("val"))
print(len(train_ds), "train /", len(val_ds), "val. Sample:\n", train_ds[0]["text"][:700])

trainer = SFTTrainer(
    model=model, tokenizer=tok, train_dataset=train_ds, eval_dataset=val_ds,
    args=SFTConfig(
        dataset_text_field="text", max_seq_length=MAX_LEN, per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=ACCUM, num_train_epochs=EPOCHS, learning_rate=LR, lr_scheduler_type="cosine",
        warmup_ratio=0.05, weight_decay=0.01, optim="adamw_8bit", seed=42,
        fp16=not __import__("torch").cuda.is_bf16_supported(), bf16=__import__("torch").cuda.is_bf16_supported(),
        logging_steps=5, eval_strategy="epoch", save_strategy="no", report_to="none", output_dir=str(OUT / "_run")))
# the loss counts only Bot's turns (every assistant turn of a multi-turn chat), never the header or the player
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n", response_part="<|im_start|>assistant\n")
stats = trainer.train()

model.save_pretrained(str(OUT))
tok.save_pretrained(str(OUT))
log = [h for h in trainer.state.log_history if "loss" in h or "eval_loss" in h]
(BASE / "scores" / f"train_{LANG}_{TIER}_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
print("train loss:", [round(h["loss"], 3) for h in log if "loss" in h][-5:], "| eval loss per epoch:",
      [round(h["eval_loss"], 3) for h in log if "eval_loss" in h])

if EXPORT_GGUF:
    # LoRA -> GGUF with llama.cpp's converter; Ollama loads it with  ADAPTER <file>  on top of the same base
    subprocess.run("git clone -q --depth 1 https://github.com/ggerganov/llama.cpp /content/llama.cpp && "
                   "pip -q install -r /content/llama.cpp/requirements/requirements-convert_lora_to_gguf.txt", shell=True)
    r = subprocess.run([sys.executable, "/content/llama.cpp/convert_lora_to_gguf.py", str(OUT), "--base", str(BASE / "models" / "hf" / BASE_MODEL), "--outfile",
                        str(OUT / f"core_allowed_{LANG}_{TIER}-lora.gguf"), "--outtype", "f16"], capture_output=True, text=True)
    print(r.stdout[-600:], r.stderr[-600:])

print("\n-> adapter in Drive:", OUT, "\n-> send Claude scores/train_%s_%s_log.json and the lines above." % (LANG, TIER))
print("Disconnect the GPU runtime now.")

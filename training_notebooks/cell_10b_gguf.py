# CELL 10b -- convert an already trained adapter to a GGUF LoRA for Ollama. CPU runtime is enough, no training.
# Needs cells 0 and 1 only (LANG, BASE). Use it when cell 10 saved the adapter but the GGUF step failed.
# Cell 0 may set TIER = "light" | "medium" | "high" (default medium).
import subprocess, sys

TIER = globals().get("TIER", "medium")
BASE_MODEL = {"light": "Qwen3-1.7B", "medium": "Qwen3-4B-Instruct-2507", "high": "Qwen3-8B"}[TIER]
OUT = BASE / "adapters" / f"core_allowed_{LANG}_{TIER}"

subprocess.run("pip -q install torch transformers safetensors gguf sentencepiece numpy", shell=True)
subprocess.run("rm -rf /content/llama.cpp && git clone -q --depth 1 https://github.com/ggerganov/llama.cpp /content/llama.cpp && "
               "pip -q install -r /content/llama.cpp/requirements/requirements-convert_lora_to_gguf.txt", shell=True)
# --base = the local base folder: without it the converter reads the path in adapter_config.json as a Hugging Face repo id
r = subprocess.run([sys.executable, "/content/llama.cpp/convert_lora_to_gguf.py", str(OUT), "--base", str(BASE / "models" / "hf" / BASE_MODEL),
                    "--outfile", str(OUT / f"core_allowed_{LANG}_{TIER}-lora.gguf"), "--outtype", "f16"], capture_output=True, text=True)
print(r.stdout[-800:], r.stderr[-800:])
print("OK ->", OUT / f"core_allowed_{LANG}_{TIER}-lora.gguf" if r.returncode == 0 else "FAILED: send Claude the lines above")

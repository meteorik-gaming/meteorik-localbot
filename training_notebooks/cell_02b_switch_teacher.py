# CELL 2b -- switch the teacher model WITHOUT redoing the whole setup (same session, GPU runtime).
# Edit NEW_TEACHER / NEW_PARALLEL, run. Use cell 2 for the first setup; use this to compare models.
#   qwen3:8b  -> NEW_PARALLEL "8"     qwen3:14b -> "6"     qwen3:32b (A100 only) -> "4"
# Afterwards set a NEW BATCH name in cell 5 (e.g. "p4b") so the files do not mix.
NEW_TEACHER = "qwen3:8b"
NEW_PARALLEL = "8"
NEW_THINK = True        # the teacher reasons first (the maintainer's local test: much better replies). False = fast, no reasoning

old_model = TEACHER
THINK = NEW_THINK                       # ask() reads this flag
server.terminate()                      # restart Ollama: the parallel setting is read at startup
server.wait()
time.sleep(2)
subprocess.run(["pkill", "-f", "ollama"], check=False)
time.sleep(2)
os.environ["OLLAMA_NUM_PARALLEL"] = NEW_PARALLEL
server = subprocess.Popen(["ollama", "serve"], env=os.environ,
                          stdout=open("/content/ollama.log", "a"), stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        requests.get(URL, timeout=1)
        break
    except Exception:
        time.sleep(1)
TEACHER = NEW_TEACHER                   # ask() reads this name, and cell 5 records it in every row
subprocess.run(["ollama", "pull", TEACHER], check=True)
print(f"teacher: {old_model} -> {TEACHER}, think={THINK}")
print(ask("Reply with JSON only.", 'Give {"ok": true}', max_tokens=20))
print(subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout)   # should say 100% GPU

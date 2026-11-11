extends Node
## Ollama — local LLM transport:
##   is_model_available()   GET  /api/tags
##   chat() / chat_stream() POST /api/chat      (stop: ["\nUser:"]) -- the game's replies
##   generate()             POST /api/generate  (stop: ["\nUser:"])
##   summarize()            POST /api/generate  (no stop)
##
## Pure transport — the prompt assembly, tag extraction and in-fiction error
## messages live in core/chat.gd (Chat). HTTPRequest is async via signal, so
## callers just `await`; a fresh request node per call keeps concurrent calls
## (chat send vs. model-availability check) from colliding.

const BASE_URL := "http://127.0.0.1:11434"
const GENERATE_URL := BASE_URL + "/api/generate"
const CHAT_URL := BASE_URL + "/api/chat"
const TAGS_URL := BASE_URL + "/api/tags"

const GENERATE_TIMEOUT := 60.0

# Safety nets so a model that never emits its end-of-turn token (a small model looping)
# cannot freeze the chat: a hard cap on tokens per reply, and on wall-clock time per
# streamed reply (GENERATE_TIMEOUT only measures silence, not total time).
const MAX_REPLY_TOKENS := 700
const MAX_REPLY_SECONDS := 120.0
const TAGS_TIMEOUT := 150.0

# Benchmark hooks (tests/model_bench.gd). The game never sets/reads these:
var bench_options := {}   # merged into generate()'s "options" (e.g. a fixed seed)
var last_raw := ""        # untouched response text of the latest generate/summarize
var last_stats := {}      # Ollama's timing fields of the latest call (durations in ns)


## Names of every locally-pulled model, or [] on any failure to reach Ollama.
func list_models() -> Array:
	var r: RequestResult = await _request(TAGS_URL, HTTPClient.METHOD_GET, "", TAGS_TIMEOUT)
	if not r.ok or not (r.data is Dictionary):
		return []
	var names: Array = []
	for entry in r.data.get("models", []):
		if entry is Dictionary:
			for key in ["name", "model"]:
				var n: String = String(entry.get(key, ""))
				if n != "" and not names.has(n):
					names.append(n)
	return names


## Ollama lists a tag given without a version as "<name>:latest" (same rule as Adapters).
func is_model_available(model_name: String) -> bool:
	var installed: Array = await list_models()
	return installed.has(model_name) or (not model_name.contains(":") and installed.has(model_name + ":latest"))


## Raw completion. Returns { ok: bool, response: String, error: String }.
func generate(full_prompt: String, model_name: String) -> Dictionary:
	var body := {
		"model": model_name,
		"prompt": full_prompt,
		"stream": false,
		"think": false,   # Qwen3 reasons by default; we want the reply only (ignored by non-thinking models)
		# Stop the instant the model starts a new "User:" turn — this is a raw
		# completion prompt, nothing else keeps it from writing (and answering)
		# a fake extra user turn. Chat.call_model has a regex safety net too.
		"options": { "stop": ["\nUser:"] },
	}
	body["options"].merge(bench_options, true)
	return await _generate_common(body)


## Same request as generate() but streamed (NDJSON, one object per chunk of
## tokens). `on_text` is called with the whole reply text so far each time more
## arrives. Returns the same { ok, response, error } shape; `response` is the
## complete text. The timeout is per silence (no bytes for GENERATE_TIMEOUT s),
## not per reply, so a long answer on a slow model isn't cut off.
func generate_stream(full_prompt: String, model_name: String, on_text: Callable) -> Dictionary:
	var body := {
		"model": model_name,
		"prompt": full_prompt,
		"stream": true,
		"think": false,
		"options": { "stop": ["\nUser:"] },
	}
	body["options"].merge(bench_options, true)
	return await _stream("/api/generate", body, on_text)


## Chat-API twin of generate(): `messages` is [{ role: system|user|assistant, content }],
## the model's own chat template wraps each turn. Same { ok, response, error } shape.
func chat(messages: Array, model_name: String) -> Dictionary:
	var body := {
		"model": model_name,
		"messages": messages,
		"stream": false,
		"think": false,
		"options": { "stop": ["\nUser:"], "num_predict": MAX_REPLY_TOKENS, "repeat_penalty": 1.15, "repeat_last_n": 256 },
	}
	body["options"].merge(bench_options, true)
	return await _generate_common(body, CHAT_URL)


## Chat-API twin of generate_stream().
func chat_stream(messages: Array, model_name: String, on_text: Callable) -> Dictionary:
	var body := {
		"model": model_name,
		"messages": messages,
		"stream": true,
		"think": false,
		"options": { "stop": ["\nUser:"], "num_predict": MAX_REPLY_TOKENS, "repeat_penalty": 1.15, "repeat_last_n": 256 },
	}
	body["options"].merge(bench_options, true)
	return await _stream("/api/chat", body, on_text)


## The streaming transport shared by generate_stream() and chat_stream().
func _stream(path: String, body: Dictionary, on_text: Callable) -> Dictionary:
	last_raw = ""
	last_stats = {}

	var client := HTTPClient.new()
	var base := BASE_URL.trim_prefix("http://").split(":")
	if client.connect_to_host(base[0], int(base[1])) != OK:
		return { "ok": false, "response": "", "error": "connect_to_host failed" }
	var idle := Time.get_ticks_msec()
	while client.get_status() in [HTTPClient.STATUS_CONNECTING, HTTPClient.STATUS_RESOLVING]:
		client.poll()
		if _stalled(idle):
			client.close()
			return { "ok": false, "response": "", "error": "connect timeout" }
		await get_tree().process_frame
	if client.get_status() != HTTPClient.STATUS_CONNECTED:
		client.close()
		return { "ok": false, "response": "", "error": "can't connect (status %d)" % client.get_status() }

	var headers := PackedStringArray(["Content-Type: application/json"])
	if client.request(HTTPClient.METHOD_POST, path, headers, JSON.stringify(body)) != OK:
		client.close()
		return { "ok": false, "response": "", "error": "request() failed" }
	idle = Time.get_ticks_msec()
	while client.get_status() == HTTPClient.STATUS_REQUESTING:
		client.poll()
		if _stalled(idle):
			client.close()
			return { "ok": false, "response": "", "error": "response timeout" }
		await get_tree().process_frame
	if not client.has_response():
		client.close()
		return { "ok": false, "response": "", "error": "no response" }
	if client.get_response_code() != 200:
		var code := client.get_response_code()
		client.close()
		return { "ok": false, "response": "", "error": "HTTP %d" % code }

	var text := ""
	var buf := PackedByteArray()
	var done := false
	idle = Time.get_ticks_msec()
	var started := idle
	while not done and client.get_status() == HTTPClient.STATUS_BODY:
		client.poll()
		if (Time.get_ticks_msec() - started) / 1000.0 > MAX_REPLY_SECONDS:
			break   # a runaway generation: keep what we have, closing the socket cancels it
		var chunk := client.read_response_body_chunk()
		if chunk.is_empty():
			if _stalled(idle):
				client.close()
				return { "ok": false, "response": text.strip_edges(), "error": "stream timeout" }
			await get_tree().process_frame
			continue
		idle = Time.get_ticks_msec()
		buf.append_array(chunk)
		var grew := false
		var nl := buf.find(10)
		while nl != -1:
			var line := buf.slice(0, nl).get_string_from_utf8().strip_edges()
			buf = buf.slice(nl + 1)
			nl = buf.find(10)
			if line == "":
				continue
			var obj = JSON.parse_string(line)
			if not (obj is Dictionary):
				continue
			if obj.has("error"):
				client.close()
				return { "ok": false, "response": text.strip_edges(), "error": String(obj["error"]) }
			var piece := _piece(obj)
			if piece != "":
				text += piece
				grew = true
			if obj.get("done", false):
				done = true
				for k in ["total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"]:
					if obj.has(k):
						last_stats[k] = obj[k]
		if grew and on_text.is_valid():
			on_text.call(text)
	client.close()
	last_raw = text.strip_edges()
	if text.strip_edges() == "" and not done:
		return { "ok": false, "response": "", "error": "empty stream" }
	return { "ok": true, "response": text.strip_edges(), "error": "" }


func _stalled(since_msec: int) -> bool:
	return (Time.get_ticks_msec() - since_msec) / 1000.0 > GENERATE_TIMEOUT


## Summary call — no stop sequence. Returns the same dict shape.
func summarize(prompt: String, model_name: String) -> Dictionary:
	return await _generate_common({ "model": model_name, "prompt": prompt, "stream": false, "think": false })


## The reply text of one response object: `response` (generate API) or
## `message.content` (chat API).
func _piece(obj: Dictionary) -> String:
	var msg = obj.get("message")
	if msg is Dictionary:
		return String(msg.get("content", ""))
	return String(obj.get("response", ""))


func _generate_common(body: Dictionary, url := GENERATE_URL) -> Dictionary:
	var r: RequestResult = await _request(url, HTTPClient.METHOD_POST, JSON.stringify(body), GENERATE_TIMEOUT)
	if not r.ok:
		return { "ok": false, "response": "", "error": r.error }
	var resp := ""
	last_stats = {}
	if r.data is Dictionary:
		resp = _piece(r.data).strip_edges()
		for k in ["total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"]:
			if r.data.has(k):
				last_stats[k] = r.data[k]
	last_raw = resp
	return { "ok": true, "response": resp, "error": "" }


func _request(url: String, method: int, body: String, timeout: float) -> RequestResult:
	var http := HTTPRequest.new()
	http.timeout = timeout
	add_child(http)

	var headers := PackedStringArray(["Content-Type: application/json"]) if body != "" else PackedStringArray()
	var err := http.request(url, headers, method, body)
	if err != OK:
		http.queue_free()
		return RequestResult.fail("request() error %d" % err)

	var res: Array = await http.request_completed
	http.queue_free()

	var result_code: int = res[0]      # HTTPRequest.Result
	var response_code: int = res[1]    # HTTP status
	var payload: PackedByteArray = res[3]

	if result_code != HTTPRequest.RESULT_SUCCESS:
		return RequestResult.fail("transport result %d" % result_code)
	if response_code < 200 or response_code >= 300:
		return RequestResult.fail("HTTP %d" % response_code)

	return RequestResult.success(JSON.parse_string(payload.get_string_from_utf8()))


class RequestResult:
	var ok: bool
	var data: Variant
	var error: String

	static func success(d: Variant) -> RequestResult:
		var r := RequestResult.new()
		r.ok = true
		r.data = d
		return r

	static func fail(e: String) -> RequestResult:
		var r := RequestResult.new()
		r.ok = false
		r.error = e
		return r

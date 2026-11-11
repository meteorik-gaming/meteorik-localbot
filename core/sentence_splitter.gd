class_name SentenceSplitter
## Splits a reply into sentences (and, on top of that, text bubbles). Used to
## release a streamed reply one sentence at a time (Chat.call_model) and as the
## plumbing for multi-bubble messages (bubbles() -- the chat log doesn't draw
## separate bubbles yet; nothing is stored, it's always derived from the text).
##
## A sentence closes at . ! ? or an ellipsis ("..." and the single char "…"
## both count -- "I am... present" is two sentences) followed by whitespace,
## allowing closers (*, quotes, brackets) between the two. "3.5" and "Dr.Smith"
## have no space after the dot, so they never cut. A newline also cuts a
## sentence. A sentence has `bubble_break` = true when its closing is followed by
## a newline: that's where a new text bubble starts.

const TERMINATORS := ".!?…"
const CLOSERS := "*\"'”’)]"


## Returns [{ "text": sentence (trimmed), "bubble_break": bool, "start": int, "end": int }].
## `start`/`end` are offsets into `text`; `end` is just past the whitespace that
## followed the sentence, so text.substr(0, items[-1].end) is "everything
## released so far".
##
## final = true  -> the unfinished tail counts as a sentence too (full reply).
## final = false -> the tail is left out: its terminator may still be extended
##                  ("." now, "..." in the next chunk), so it isn't safe to show.
static func split(text: String, final := true) -> Array:
	var out: Array = []
	var n := text.length()
	var start := 0
	var i := 0
	while i < n:
		var c := text[i]
		if c == "\n":
			var cut := text.substr(start, i - start).strip_edges()
			var j := _skip_space(text, i)
			if cut != "":
				out.append({ "text": cut, "bubble_break": false, "start": start, "end": j })
			start = j
			i = j
			continue
		if TERMINATORS.contains(c):
			var j := i + 1
			while j < n and TERMINATORS.contains(text[j]):
				j += 1
			while j < n and CLOSERS.contains(text[j]):
				j += 1
			if j < n and _is_space(text[j]):
				var k := _skip_space(text, j)
				var gap := text.substr(j, k - j)
				out.append({
					"text": text.substr(start, j - start).strip_edges(),
					"bubble_break": gap.contains("\n"),
					"start": start, "end": k,
				})
				start = k
				i = k
				continue
			i = j
			continue
		i += 1
	if final:
		var tail := text.substr(start).strip_edges()
		if tail != "":
			out.append({ "text": tail, "bubble_break": false, "start": start, "end": n })
	return out


## Groups sentences into bubbles: [{ "text": String, "sentences": [String] }].
## A bubble ends after a sentence flagged bubble_break (and at the end of the
## text). Joining the bubbles with newlines gives back the reply, modulo
## whitespace; a text with no breaks is one bubble (old saves, plain replies).
static func bubbles(text: String) -> Array:
	var out: Array = []
	var cur: Array[String] = []
	for item in split(text, true):
		cur.append(item["text"])
		if item["bubble_break"]:
			out.append({ "text": " ".join(cur), "sentences": cur })
			cur = []
	if not cur.is_empty():
		out.append({ "text": " ".join(cur), "sentences": cur })
	return out


## What can be shown of a streamed reply so far: the text up to the end of the
## last COMPLETE sentence ("" if none yet).
static func released(text: String) -> String:
	var items := split(text, false)
	if items.is_empty():
		return ""
	return text.substr(0, items[-1]["end"]).strip_edges()


static func _is_space(ch: String) -> bool:
	return ch == " " or ch == "\n" or ch == "\t" or ch == "\r"


static func _skip_space(text: String, from: int) -> int:
	var j := from
	while j < text.length() and _is_space(text[j]):
		j += 1
	return j

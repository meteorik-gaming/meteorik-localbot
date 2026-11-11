class_name Memory
## The memory system: the summary prompt template (summarize-on-save) and
## apply_fuzziness (recall-time, once: per-sentence forget/hedge).
##
## The sentence split is a search_all + slicing, since Godot RegEx has lookbehind
## (PCRE2) but no split().

const SUMMARY_WORD_CAP := 120
const FORGET_CHANCE := 0.15   # per-sentence chance a detail just doesn't come up
const HEDGE_CHANCE := 0.25    # per-sentence chance of a hedging qualifier
const HEDGES := ["I think ", "If I'm remembering right, ", "Pretty sure ", "I want to say "]

const SUMMARY_PROMPT := "Summarize the key facts, events, and emotional beats from the conversation below in {cap} words or fewer, from Bot's own perspective, as things worth remembering about this specific relationship/thread going forward. Focus on concrete facts (what happened, what the user revealed about themselves, notable moments) rather than restating mood or tone. Write it as plain prose in a few sentences, not a list, and do not include any bracketed tags.\n\nConversation:\n{transcript}"

static var _re_sentence_split := RegEx.create_from_string(r'(?<=[.!?])\s+')


static func summary_prompt(transcript: String) -> String:
	return SUMMARY_PROMPT.replace("{cap}", str(SUMMARY_WORD_CAP)).replace("{transcript}", transcript)


## Split into sentences and rejoin with single spaces — the deterministic core
## of apply_fuzziness, with no forget/hedge randomness.
static func reflow(summary_text: String) -> String:
	if summary_text.strip_edges().is_empty():
		return summary_text
	return " ".join(_sentences(summary_text))


## Applied ONCE at recall (load) time — each sentence has a chance to be dropped
## or get a hedging qualifier prepended.
static func apply_fuzziness(summary_text: String) -> String:
	if summary_text.strip_edges().is_empty():
		return summary_text
	var kept: Array[String] = []
	for sentence in _sentences(summary_text):
		if randf() < FORGET_CHANCE:
			continue
		if randf() < HEDGE_CHANCE:
			var hedge: String = HEDGES[randi() % HEDGES.size()]
			sentence = hedge + sentence.substr(0, 1).to_lower() + sentence.substr(1)
		kept.append(sentence)
	return " ".join(kept)


static func _sentences(text: String) -> PackedStringArray:
	var stripped := text.strip_edges()
	var pieces := PackedStringArray()
	var last := 0
	for m in _re_sentence_split.search_all(stripped):
		pieces.append(stripped.substr(last, m.get_start() - last))
		last = m.get_end()
	pieces.append(stripped.substr(last))

	var out := PackedStringArray()
	for p in pieces:
		var s := p.strip_edges()
		if not s.is_empty():
			out.append(s)
	return out


## Sanitize + hard-cap a generated summary (matches bot_generate_memory_summary).
static func sanitize_summary(summary: String) -> String:
	summary = summary.replace("[", "").replace("]", "")
	# Python str.split() splits on any whitespace run and drops empties.
	var words := summary.replace("\n", " ").replace("\t", " ").replace("\r", " ").split(" ", false)
	if words.size() > SUMMARY_WORD_CAP:
		return " ".join(words.slice(0, SUMMARY_WORD_CAP))
	return summary

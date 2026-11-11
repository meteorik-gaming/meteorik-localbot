class_name Axes
## Tuning for every live axis, in one place. All axes run -10..10 with 0 neutral
## (stored as 0..100 meters where noted; Meters.to_axis / from_axis convert).
##
## Every axis works the same way: a reply produces a TARGET from the AI's tags, and
## the axis closes `rate` of the gap to it (step). A fast rate is a mood, a slow one
## is a relationship. Sustained input settles on the target; silence drifts to 0
## (energy drifts to her routine instead).
##
## NOTE: the whole system needs a rebalance pass for this logic (rates, targets,
## trust deltas, ladder thresholds). The numbers below are first guesses.

# ---- mood axes (fast) ------------------------------------------------------

# y, agreeableness: what the AI's [affinity:] tag pulls her feel toward.
const FEEL_TARGETS := {
	"hate": -10.0, "dislike": -7.0, "bothers": -3.0, "neutral": 0.0,
	"enjoys": 3.0, "likes": 7.0, "loves": 10.0,
}
const FEEL_RATE := 0.5

# z, excitation: what the AI's [excitation:] tag pulls her toward. Nothing
# ("none") is null, not negative; only off-putting behavior (the catalog's
# violation signals, creepy / weird advances) sends the axis cold.
const EXCITE_TARGETS := {
	"none": 0.0, "mild": 2.0, "building": 5.0, "strong": 8.0, "peak": 10.0,
}
const EXCITE_RATE := 0.4
const EXCITE_POSITIVE_BONUS := 3.0   # catalog "positive" signal: aim higher
const EXCITE_VIOLATION_TARGET := -7.0
const EXCITE_BOUNDARY_TARGETS := { "mild": -4.0, "severe": -7.0 }   # the AI flagged a boundary push

# x, energy: the [mood:] tag pushes it; regression pulls it to her routine baseline.
# Sustained, a tag settles at baseline + 5 * delta meter points (`delta` axis units).
const ENERGY_DELTAS := {
	"neutral": 0, "calm": -7, "happy": 7, "annoyed": 7, "alert": 8,
}
const ENERGY_REGRESSION := 0.2

# ---- relationship axes (slow, saved per game) -------------------------------

# Bond gains get harder as the bond grows: strangers become friends easily, friends become a
# couple slowly, a couple become married very slowly. [bond below, multiplier on gains]; losses
# are not slowed. Calibrated against the healthy run in tests/trajectory_test (30 messages, an
# hour of chat, move a Realistic bond about 25 points).
const BOND_FRICTION := [[75.0, 1.2], [88.0, 0.25], [96.0, 0.12], [101.0, 0.06]]

# Presence (trust): days in a row she has heard from the player. Each missed day halves the
# streak (rounded down). Trust gains grow up to PRESENCE_MAX_BONUS over PRESENCE_MAX_DAYS days;
# after PRESENCE_AWAY_DAYS days of silence trust gains run slower (PRESENCE_DIP) until the
# streak is back to PRESENCE_RECOVER_DAYS. Bond and trust already earned never drop from absence.
const PRESENCE_MAX_DAYS := 8
const PRESENCE_MAX_BONUS := 0.5
const PRESENCE_AWAY_DAYS := 7
const PRESENCE_DIP := 0.85
const PRESENCE_RECOVER_DAYS := 3

# Heat gains: a session warms up (SESSION_START of the gain on the first message, full at
# SESSION_WARM_MESSAGES), a gap of SESSION_GAP_SECONDS starts a new session. Her busyness
# (data/routines.gd) gates it: free up to HEAT_BUSY_FREE, down to HEAT_BUSY_FLOOR at HEAT_BUSY_BLOCKED.
const SESSION_GAP_SECONDS := 1800.0
const SESSION_START := 0.4
const SESSION_WARM_MESSAGES := 12
const HEAT_BUSY_FREE := 3.0
const HEAT_BUSY_BLOCKED := 8.0
const HEAT_BUSY_FLOOR := 0.1

# bond = Meters affinity_hate_love, heat = Meters excitation_meter (both 0..100, with
# their own slow update in Meters). trust is the third one:
const TRUST_BY_AFFINITY := {
	"hate": -3.0, "dislike": -2.0, "bothers": -1.0, "neutral": 0.0,
	"enjoys": 0.5, "likes": 1.0, "loves": 1.5,
}
# Staying quiet earns nothing; only warmth builds trust, and a push costs far more than a kind reply earns.
const TRUST_BOUNDARY := { "none": 0.0, "mild": -3.0, "severe": -8.0 }   # meter points


static func step(value: float, target: float, rate: float) -> float:
	return value + (target - value) * rate

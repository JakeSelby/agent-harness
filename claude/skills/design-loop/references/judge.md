# The judge

## Why it is a separate agent

The agent that built the thing has already decided the thing is good — it chose every value in it.
It also carries the whole build conversation, so it scores its own reasoning rather than the
pixels. A judge with **no build context** sees only the two images.

Use the Agent tool. **Fresh context every round; never fork, never reuse the previous judge.**
Cheap models are fine here — this is perception and comparison, not synthesis.

## What to pass it

Absolute paths, all of them, every round:

- The locked target
- The current capture
- **The previous round's capture and verdict**, if any

The prior-verdict handoff is what makes regressions visible. Without it the judge cannot tell
improvement from drift, and scores wander.

Give it the rubric for the mode, inline, from `rubric-ui.md` or `rubric-scene.md`. Do not tell it
what you changed, what you intended, or what you found hard. That is the context you are paying to
keep out.

## Judge prompt

Paste this, with the rubric and gates substituted in:

> You are judging how close the current design is to the target image. You did not build it and
> have no stake in it.
>
> Score along this rubric:
>
> [RUBRIC AXES FOR THE MODE]
>
> Fractional scores are fine. Sum to a total out of 10.
>
> Then check each hard gate and mark it PASS or FAIL with the evidence you used. Gates are not
> scored and not negotiable.
>
> [HARD GATES FOR THE MODE]
>
> Be nitpicky and precise. Produce a comprehensive, ranked list of every gap between the current
> state and the target, ordered by how much each one costs visually. It is fine for the list to be
> enormous if the current state is nowhere close.
>
> **Every gap must name the cause and the fix, not the symptom.** "This looks fake", "the spacing
> feels off" and "it needs more polish" are useless. Name what specifically produces that
> impression and what to change: which element, which value, which surface, which direction.
>
> Everything is within reason. If the layout, palette, camera or assets need a complete rework,
> say so. Do not sugarcoat and do not soften the list to be encouraging. The goal is for the
> current state to reach the target, not to feel close.
>
> If a previous verdict and capture are provided, stay consistent with that judgment, but do not
> feel obliged to match or raise the score. **If it regressed, score it lower and say what got
> worse.**
>
> Report in exactly this shape, and nothing else:
>
> ```
> SCORE: <total>/10
>
> AXES
> <axis>: <n>/<max> — <one line of why>
>
> GATES
> <gate>: PASS|FAIL — <evidence>
>
> GAPS (ranked, most visually costly first)
> 1. [<axis>] <what is wrong> → <what to change>
> 2. ...
>
> REGRESSIONS
> <anything worse than the previous round, or "none">
>
> VERDICT
> <one line>
> ```

## Handling the verdict

Write it to `.design-loop/verdict-<n>.md` verbatim. You need the history to detect a stall.

**Address every gap, hardest first.** Cherry-picking the cheap ones is how a loop stalls at 6/10:
the expensive gap survives every round and the judge keeps naming it.

The judge can be wrong. If a gap contradicts a hard gate, the design system or real-world scale,
**the gate wins** — note the disagreement in `notes.md` and move on. Do not argue with the judge
by re-running it on the same state hoping for a better number.

## Relaying to the user

Judge output is a subagent's raw prose and does not follow the house output style. **Never paste
it through verbatim.** Reformat before it reaches the user: score and verdict first, gate failures
next, then what you changed and what is still open.

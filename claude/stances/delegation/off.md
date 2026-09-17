# Delegation stance: off

Do not spawn subagents unless the user asks. Do the work inline. If a task genuinely exceeds one
context window, say so and propose a fan-out rather than starting one. The `tier-spawns` hook
asks before any spawn under this stance, so the user's yes is the only way one starts.

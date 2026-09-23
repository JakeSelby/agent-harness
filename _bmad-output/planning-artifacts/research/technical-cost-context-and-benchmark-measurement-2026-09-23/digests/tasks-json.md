# Digest: benchmarks/tasks.json (at 3020251), summarised not copied

- claim: The manifest now holds eight tasks: six issue-derived (each a parent commit plus the fixing commit, scored by copied held-back tests) and two synthetic (many-file read-and-summarise `hook-inventory`, multi-module mechanical edit `hook-ids`) scored by oracles; every task caps at 60 turns.
  source: benchmarks/tasks.json
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method

- claim: Each task carries a `leak_class`: one `leaks` (link-alias), one `control` (cost-variants), six `clean`; the docs still describe a four-task default schedule, and no history.jsonl or results file is committed under benchmarks/.
  source: benchmarks/tasks.json; directory listing of benchmarks/
  publisher: agent-harness
  pub_date: 2026-09-22
  accessed: 2026-09-23
  confidence: high
  class: method

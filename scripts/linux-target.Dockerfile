# The container the Linux qualification targets run in, `claude-code-cli-linux` and
# `codex-cli-linux`, on a host that is not Linux. What it must provide and how a round uses it is
# in docs/qualification-runbook.md; this file only pins the two clients.
#
# The base is Docker's Codex sandbox template (Ubuntu, a non-root `agent` user, Node and Python),
# pinned to the digest the 0.11.x Linux rounds were built from. Each client is installed from npm
# at the exact version the round records, so bump both arguments together with the catalog.
#
#   docker build -f scripts/linux-target.Dockerfile -t agent-harness-linux-target .
#   docker build -f scripts/linux-target.Dockerfile --platform linux/amd64 \
#       -t agent-harness-linux-target:amd64 .
#
# The build context carries nothing into the image; the frozen clone is mounted at run time.
FROM docker/sandbox-templates:codex@sha256:a68b972a59148c6359ade441387159033f6d196d48aef9dda06d2d4bb26eb41e

ARG CODEX_VERSION=0.155.1
ARG CLAUDE_CODE_VERSION=2.1.278

USER agent
RUN npm install -g "@openai/codex@${CODEX_VERSION}" "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}"

CMD ["bash"]

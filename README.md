# AgentDeck

One screen on your phone: every coding agent, one view — task state, file ops,
terminal output, progress, plus a daily AI digest.

Built for [DEV Hacktoberfest Week 2 (2026)](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)
— theme: **Side Hustle** (open-source AI someone would actually pay for).

## Layout

- `collector/` — MCP client that polls the phone-bridge MCP servers (Prisma,
  Railway) and snapshots agent activity into `collector/snapshots/`.
- `dashboard/` — phone-first web UI (coming Day 2).

## Day 1 status

- [x] New repo created within the challenge window
- [x] Collector talks to both bridges and pulls the first real activity stream
- [ ] Phone dashboard UI (Day 2)

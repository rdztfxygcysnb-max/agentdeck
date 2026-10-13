# AgentDeck

One screen on your phone: every coding agent, one view — task state, file ops,
terminal output, progress, plus a daily AI digest.

Built for [DEV Hacktoberfest Week 2 (2026)](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)
— theme: **Side Hustle** (open-source AI someone would actually pay for).

## Layout

- `collector/` — MCP client that polls the phone-bridge MCP servers (Prisma,
  Railway) and snapshots agent activity into `collector/snapshots/`.
  Runs hourly via cron; the dashboard always reads `snapshots/latest.json`.
- `dashboard/` — phone-first static web UI (no backend, no sleep):
  deploy to Cloudflare Pages, reads the latest snapshot and renders
  one card per bridge: status, tools, recent activity.

## Day 1 status

- [x] New repo created within the challenge window
- [x] Collector talks to both bridges and pulls the first real activity stream
- [x] Hourly snapshot cron set (keeps newest 48, auto-pushes to main)
- [x] Static dashboard scaffold (warm-paper theme, rubber-band motion)
- [ ] Phone dashboard UI polish (Day 2)
- [ ] Deploy to Cloudflare Pages + .tech domain (Day 4)

# AgentDeck — DRAFT (DEV submission post, English)

> Status: draft. TODOs marked [TODO]. Do not publish before Day 6 review.

---

# I run 4 coding agents on my phone. I built the 5th screen.

I run Claude Code, Codex, and OpenCode across a cloud VM, a Railway box, and a
phone-bridge MCP server. To see what they're doing, I had four terminal windows
and zero global view.

So I built **AgentDeck**: one screen on your phone that shows every coding
agent — task state, file operations, terminal output, progress — plus one
AI-written line: *"here's what your fleet did today."*

[TODO: demo GIF — fleet view + daily digest push screenshot]

## Who would pay for this?

Anyone running an agent fleet. Right now they SSH into boxes and squint at
separate TUIs. A hosted dashboard + daily push digest at **$8/month** is an
easy sell — the same "small money for peace of mind" logic as Uptime Kuma or
a RunGPU panel.

The unit economics work because the summary layer is open-weight:

| Item | Cost |
|---|---|
| Daily digest per agent (Gemma via API) | a fraction of a cent |
| 10 agents × 30 days | well under $1/month |
| Subscription | $8/month |

Open models make the small business add up. A closed API at 10× the token
price would kill the margin — openness is the business model, not the
marketing.

## Why open innovation matters here (the part the judges asked for)

1. **MCP, not vendor lock-in.** The collector is an MCP *client*. It talks to
   any MCP server — mine today, yours tomorrow. If a vendor changes pricing or
   kills an endpoint, I swap the bridge, not the product.
2. **Open weights make the math work.** The digest runs on Gemma (open-weight,
   served through a provider — explicitly allowed). Pennies a day per agent.
3. **Self-hostable by design.** Agent data never has to leave your own
   infrastructure. The whole thing is a static site plus a poller you can run
   on a cron job anywhere.

## Build log (6 days)

- **Day 1:** New repo. MCP collector polls two live phone-bridge servers
  (Prisma + Railway) over Streamable HTTP and snapshots activity hourly.
  First real activity stream pulled the same day.
- **Day 2:** Phone-first dashboard — warm-paper theme, bouncy physics,
  one card per bridge: status, tools, recent activity.
- **Day 3:** Gemma digest layer — hourly one-liners plus a daily fleet report.
- **Day 4:** Deployed to Cloudflare Pages + free .tech domain. Dogfooded it
  myself the same evening.
- **Day 5:** First external user — [TODO: what happened in the 10-minute trial,
  what they asked, what I changed].
- **Day 6:** This post.

What got cut (honest): [TODO — e.g. push notifications v1, multi-user auth].
The judges like knowing what you killed.

## Prize categories

- Best Use of Gemma ($200) — open-weight digest layer
- Best Use of MongoDB Atlas ($100) — [TODO: if wired] long-term agent memory
- Best Use of Sentry Agent Tracing ($100) — [TODO: if wired] agent observability
- Best Use of a .tech Domain ($100) — live demo on [TODO: domain]
- Best Use of Entire ($100) — [TODO: if wired] embedded agent session via DevRelay

## Links

- Repo: https://github.com/rdztfxygcysnb-max/agentdeck
- Live demo: [TODO: .tech domain]

---

*Built for the DEV Hacktoberfest Week 2 challenge "Side Hustle":
open-source AI someone would actually pay for.*

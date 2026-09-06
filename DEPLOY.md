# Deploying MediKiosk

The API and the built React app ship as **one service on one origin**. The client
calls a relative `/api`, which only works in development because Vite proxies it —
deployed separately, those calls hit the static host and 404. One service also
means no CORS and the websocket on the same host.

```bash
docker build -t medikiosk .
docker run -p 8000:8000 -e GEMINI_API_KEY=your_key medikiosk
# http://localhost:8000
```

## Required configuration

| Variable | Needed for | Without it |
|---|---|---|
| `GEMINI_API_KEY` | Document OCR (vision) | Intake still works; scanning does not |
| `GROQ_API_KEY` | Conversation, CDSS (text) | Falls back to the deterministic engine |
| `PORT` | Set by most hosts automatically | Defaults to 8000 |

**Never commit `.env`.** Set these as platform secrets. `.env` is gitignored and
excluded from the image by `.dockerignore`.

## Where to host

The constraint is no spin-down, so anything that sleeps after minutes of idling
is out. Free-tier terms change often — verify current limits before relying on
these.

| Host | Sleeps? | Notes |
|---|---|---|
| **Hugging Face Spaces** (Docker) | After ~48h idle | Easiest free option. WebSockets work. Plausible home for an AI project. |
| **Oracle Cloud Always Free** | Never | A real VM, genuinely free. Best technically; needs manual setup, and instance capacity is often unavailable. |
| **Koyeb** | No (free instance) | Straightforward Docker deploy. |
| **Fly.io** | Configurable (`min_machines_running = 1`) | Good, but the free allowance may not cover an always-on machine. |

Avoid for the backend: Vercel and Netlify (serverless, no WebSockets, no
persistent process), and anything that sleeps after minutes.

## Deploying to Hugging Face Spaces (step by step)

**1. Create the Space.** huggingface.co → your profile → New Space.
Name it `medikiosk`, SDK **Docker** → *Blank*, visibility Public (private Spaces
sleep more aggressively). Hardware: the free CPU basic tier.

**2. Add the Space frontmatter.** A Docker Space reads its configuration from a
YAML block at the very top of `README.md`. Without it the Space will not start.
Add this as the **first lines** of `README.md`, before anything else:

```yaml
---
title: MediKiosk
emoji: 🩺
colorFrom: teal
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
```

**3. Add the Space as a git remote and push.**

```bash
git remote add space https://huggingface.co/spaces/<your-username>/medikiosk
git push space feat/doctor-portal:main
```

Hugging Face asks for a username and an access token as the password — create
one at Settings → Access Tokens with **write** permission. Your GitHub password
will not work.

**4. Set the API keys as secrets.** Space → Settings → *Variables and secrets* →
New secret. Add `GEMINI_API_KEY`, and `GROQ_API_KEY` if you use it. Use
**Secret**, not Variable — variables are visible to anyone viewing the Space.

**5. Watch the build.** The Logs tab shows the Docker build. First build takes
several minutes because it installs npm and pip dependencies. When it finishes
the app is at `https://<username>-medikiosk.hf.space`.

### If it fails to start

| Symptom | Cause |
|---|---|
| Space stuck on "Building" then errors | Read the Logs tab — usually a dependency failing to install |
| App builds but the page never loads | `app_port` in the frontmatter does not match the port uvicorn binds (7860) |
| `Permission denied` writing the database or uploads | The image must run as UID 1000; ours does via `USER appuser` |
| Scanning fails but intake works | `GEMINI_API_KEY` missing from Space secrets, or the daily quota is spent |

### Known limits on the free tier

- The filesystem resets on restart, so uploaded documents and `medikiosk.db` do
  not persist. Seeded demo patients come back on boot.
- The Space sleeps after roughly 48 hours idle. Open the URL the morning of any
  demo so the first visitor is not waiting on a cold start.

## Things that will bite you

**State lives in process memory.** The dispatch ledger, bed board, doctor tokens
and the in-memory event index are all lost on restart. Fine for a demo; a restart
mid-judging is not. Events do persist to SQLite, so the audit trail survives.

**The filesystem is ephemeral on most free hosts.** Uploaded documents and
`medikiosk.db` disappear on redeploy. Mount a volume if the platform offers one.

**Gemini's free tier allows 20 requests per day**, shared across everyone using
the deployment. A handful of visitors exhausts it and scanning stops working for
the rest of the day. Enable billing (Flash costs a fraction of a rupee per image)
before putting the URL in front of judges.

## Rebuilding the frontend

The image builds it. Locally, the API only serves the UI if `frontend/dist`
exists:

```bash
cd frontend && npm run build
```

Otherwise `/` returns a JSON notice pointing at `/docs`.

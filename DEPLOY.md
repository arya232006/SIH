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

The constraint is no spin-down. Free-tier terms change often and have been
contracting — verify current limits before relying on any of this.

| Host | Verdict |
|---|---|
| **Render** (what we use) | Free, Docker-native, no card. Sleeps after 15 min idle, which an external pinger solves — see below. |
| **Koyeb** | Free instance, Docker, does not sleep. Good alternative. |
| **Fly.io** | Docker, `min_machines_running = 1` prevents idling. Requires a card. |
| **Oracle Cloud Always Free** | Best technically: a real VM that never sleeps, with a persistent disk. ARM instance capacity is frequently unavailable, so not something to depend on against a deadline. |

**Hugging Face Spaces does not work for this project.** Docker Spaces are a paid
feature, and free Gradio Spaces run on ZeroGPU, which is built for on-demand GPU
functions rather than an always-on server with websockets. Static Spaces cannot
run Python at all.

Avoid for the backend: Vercel and Netlify — serverless, no websockets, no
persistent process.

## Deploying to Render

Render's free plan is Docker-native, needs no card, and spins down after 15
minutes without traffic. That last part is fixed below.

**1. Create the service.** render.com → New → **Blueprint** → connect the GitHub
repo → it reads `render.yaml` and configures everything. Approve.

Using the Blueprint rather than clicking through the dashboard means the
configuration is versioned with the code.

**2. Supply the keys when prompted.** `render.yaml` marks them `sync: false`, so
Render asks for `GEMINI_API_KEY` and `GROQ_API_KEY` at creation and never stores
them in the repo. They can be edited later under Environment.

**3. Wait for the first build.** Several minutes: it installs npm and pip
dependencies and builds the frontend inside the image. The URL will look like
`https://medikiosk.onrender.com`.

Every push to `main` redeploys automatically (`autoDeploy: true`).

### Stopping it from sleeping

The free plan sleeps after 15 minutes idle and takes about a minute to wake --
long enough to lose a judge's attention. Keep it awake with an external pinger:

1. Sign up at **uptimerobot.com** (free) or **cron-job.org** (free).
2. Add an HTTP(s) monitor for `https://<your-service>.onrender.com/api/healthz`.
3. Interval: **5 minutes** (any value under 15 works).

`/api/healthz` is unauthenticated and cheap, so this costs nothing meaningful.

The arithmetic works out: the free plan allows 750 instance-hours per month
across all free services, and one service running continuously uses about 730.
So a single always-on service fits, but a second free service would not.

### If it fails

| Symptom | Cause |
|---|---|
| Build fails installing dependencies | Read the build log; usually a package needing a system library |
| Deploys, then health check fails | The app must listen on `$PORT`, which the Dockerfile already honours |
| App loads, scanning does not work | `GEMINI_API_KEY` missing, or the daily quota is spent |
| First request after idle takes ~60s | The pinger is not running, or its interval is over 15 minutes |

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

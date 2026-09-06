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

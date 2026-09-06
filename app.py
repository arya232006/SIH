"""
Hugging Face Spaces entrypoint.

Docker Spaces are a paid feature, so this Space uses the free Gradio SDK. That
SDK simply runs `app.py` and serves whatever binds port 7860 -- it does not
require the app to be a Gradio interface. So we start the real FastAPI
application here instead, which already serves the built React frontend on the
same origin.

Differences from the Docker deployment, both handled in this repo:
  - No build step on the Space, so frontend/dist is committed on this branch
    rather than built during deploy.
  - System packages come from packages.txt (libgl1 for PDF rendering) instead of
    apt-get in a Dockerfile.
"""
import os
import sys

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)          # SQLite and uploads resolve relative to backend/

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))

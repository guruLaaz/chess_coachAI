"""Local dev launcher — starts Redis+Postgres via Docker, builds frontend,
starts Flask + Celery worker.

Usage:
    python dev.py               # rebuild frontend + start everything
    python dev.py --skip-build  # skip frontend build (faster restart)
"""

import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
FLASK_PORT = "5050"


def run(desc, cmd, cwd=ROOT, check=True):
    print(f"\n{'='*60}")
    print(f"  {desc}")
    print(f"  $ {cmd}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if check and result.returncode != 0:
        print(f"\nFAILED: {desc}")
        sys.exit(1)


def main():
    skip_build = "--skip-build" in sys.argv

    # 1. Start Redis and Postgres via Docker (if not already running)
    run("Starting Redis + Postgres (Docker)",
        "docker-compose up -d redis postgres migrate")

    # 2. Build frontend
    if not skip_build:
        run("Installing frontend dependencies", "npm install", cwd=FRONTEND)
        run("Building Vue SPA", "npm run build", cwd=FRONTEND)
    else:
        dist = os.path.join(ROOT, "static", "dist", "index.html")
        if not os.path.exists(dist):
            print("No build found at static/dist/index.html — building anyway")
            run("Installing frontend dependencies", "npm install", cwd=FRONTEND)
            run("Building Vue SPA", "npm run build", cwd=FRONTEND)

    # .env has Docker hostnames (redis://redis, postgres://postgres).
    # Read .env, rewrite hostnames to localhost, and prevent Flask from
    # re-loading .env (FLASK_SKIP_DOTENV=1).
    local_env = {**os.environ, "FLASK_SKIP_DOTENV": "1"}

    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    key, val = key.strip(), val.strip()
                    # Rewrite Docker service hostnames to localhost
                    val = val.replace("://redis:", "://localhost:")
                    val = val.replace("://postgres:", "://localhost:")
                    val = val.replace("@postgres:", "@localhost:")
                    local_env[key] = val

    # 3. Start Celery worker in background
    print(f"\n{'='*60}")
    print("  Starting Celery worker")
    print(f"{'='*60}\n")
    celery = subprocess.Popen(
        [sys.executable, "-m", "celery", "-A", "worker.celery_app",
         "worker", "--loglevel=info", "--concurrency=1"],
        cwd=ROOT,
        env=local_env,
    )

    # 4. Start Flask (foreground)
    print(f"\n{'='*60}")
    print(f"  Starting Flask on port {FLASK_PORT}")
    print(f"  http://localhost:{FLASK_PORT}")
    print(f"{'='*60}\n")
    flask = None
    try:
        flask = subprocess.Popen(
            [sys.executable, "-m", "flask", "--app", "app", "run",
             "--port", FLASK_PORT, "--debug"],
            cwd=ROOT,
            env=local_env,
        )
        flask.wait()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        for proc in [flask, celery]:
            if proc is None:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

    print("Done.")


if __name__ == "__main__":
    main()

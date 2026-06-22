"""
Multi-company job alert with local AI relevance filtering.

Polls each configured company's job board (Ashby, Greenhouse, or Lever),
detects new postings, optionally filters them for relevance with a local
Ollama model, and notifies via macOS notification and ntfy push. Every new
posting is archived to all_new_jobs.log regardless of the filter outcome.

All data sources are free and keyless; the AI model runs locally via Ollama.
See README.md for setup.
"""

import json
import os
import re
import subprocess
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ============================ CONFIGURATION ===============================

# Secret loaded from .env (gitignored), never hardcoded in source.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct"  # must match a model from `ollama list`

PROFILE_DESCRIPTION = """
A final-year Computer Engineering student with experience in computer
vision and object detection (YOLOv5s, UAV imagery), deep learning, NLP,
and generative AI / LLMs (PyTorch, HuggingFace, LangChain). Interested in
roles like: AI/ML Engineer, Machine Learning Engineer, Data Scientist,
Applied Scientist, AI Research, Computer Vision Engineer, or general
Software Engineer roles with an ML/data focus.

NOT interested in: Sales, Business Development, Customer Success,
Security Operations (SOC), Marketing, Account Executive, or
non-technical roles.
"""

# One entry per company. "platform" is "ashby", "greenhouse", or "lever";
# "board_id" is the company token from its careers URL (see ADDING_COMPANIES.md).
# "notify_all": True bypasses the AI filter and alerts on every new posting.
COMPANIES = [
    {"name": "Atlan", "platform": "ashby", "board_id": "atlan", "notify_all": True},
    # {"name": "ExampleCo", "platform": "greenhouse", "board_id": "examplecoboardtoken"},
    # {"name": "AnotherCo", "platform": "lever", "board_id": "anotherco"},
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_JOBS_FILE = os.path.join(SCRIPT_DIR, "seen_jobs.json")
ALL_NEW_JOBS_LOG = os.path.join(SCRIPT_DIR, "all_new_jobs.log")

# ============================================================================


def strip_html(text):
    return re.sub(r"<[^>]+>", " ", text or "")


# Platform adapters: each normalizes its platform's payload into the common
# shape {title, location, url, description}.

def parse_ashby_jobs(payload):
    jobs = payload.get("jobs", [])
    return [
        {
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "url": j.get("jobUrl", ""),
            "description": j.get("descriptionPlain", ""),
        }
        for j in jobs
    ]


def fetch_ashby_jobs(board_id):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board_id}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return parse_ashby_jobs(r.json())


def parse_greenhouse_jobs(payload):
    jobs = payload.get("jobs", [])
    out = []
    for j in jobs:
        location = j.get("location") or {}
        out.append(
            {
                "title": j.get("title", ""),
                "location": location.get("name", "") if isinstance(location, dict) else "",
                "url": j.get("absolute_url", ""),
                "description": strip_html(j.get("content", "")),
            }
        )
    return out


def fetch_greenhouse_jobs(board_id):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs?content=true"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return parse_greenhouse_jobs(r.json())


def parse_lever_jobs(payload):
    out = []
    for j in payload:  # Lever returns a bare list, not wrapped in a key
        categories = j.get("categories") or {}
        out.append(
            {
                "title": j.get("text", ""),
                "location": categories.get("location", "") if isinstance(categories, dict) else "",
                "url": j.get("hostedUrl", ""),
                "description": j.get("descriptionPlain") or strip_html(j.get("description", "")),
            }
        )
    return out


def fetch_lever_jobs(board_id):
    url = f"https://api.lever.co/v0/postings/{board_id}?mode=json"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return parse_lever_jobs(r.json())


PLATFORM_FETCHERS = {
    "ashby": fetch_ashby_jobs,
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
}


def load_seen_job_ids():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_job_ids(job_ids):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(sorted(job_ids), f, indent=2)


def log_every_new_job(job, status):
    line = f"{datetime.now().isoformat()} | {status} | {job['company']} | {job['title']} | {job['url']}\n"
    with open(ALL_NEW_JOBS_LOG, "a") as f:
        f.write(line)


def check_relevance_with_ollama(job):
    """Fails open: if Ollama is unreachable, treat the job as relevant rather
    than risk silently dropping a real opportunity."""
    prompt = f"""You are filtering job postings for a candidate.

Candidate profile:
{PROFILE_DESCRIPTION}

Job posting:
Company: {job['company']}
Title: {job['title']}
Description: {job['description'][:1500]}

Question: Is this job posting relevant to the candidate's profile and
interests above? Respond with exactly one word: RELEVANT or NOT_RELEVANT."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip().upper()
        return ("RELEVANT" in answer and "NOT_RELEVANT" not in answer), True
    except Exception as e:
        print(f"  (Ollama unavailable, defaulting to notify: {e})")
        return True, False


def _escape_applescript(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def send_mac_notification(title, message):
    script = f'display notification "{_escape_applescript(message)}" with title "{_escape_applescript(title)}"'
    try:
        subprocess.run(["osascript", "-e", script], check=True, timeout=10)
    except Exception as e:
        print(f"  (Mac notification failed: {e})")


def send_android_push(title, message, url=None):
    headers = {"Title": title}
    if url:
        headers["Click"] = url
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=15,
        )
    except Exception as e:
        print(f"  (Android push failed: {e})")


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not NTFY_TOPIC:
        print(f"[{timestamp}] ERROR: NTFY_TOPIC is not set. Copy .env.example to .env "
              f"and set NTFY_TOPIC before running.")
        return

    seen_ids = load_seen_job_ids()
    current_ids = set()
    new_jobs = []
    fetch_failed = False

    for company in COMPANIES:
        fetcher = PLATFORM_FETCHERS.get(company["platform"])
        if not fetcher:
            print(f"[{timestamp}] Unknown platform '{company['platform']}' for {company['name']}, skipping.")
            fetch_failed = True
            continue
        try:
            jobs = fetcher(company["board_id"])
        except Exception as e:
            print(f"[{timestamp}] Failed to fetch {company['name']}: {e}")
            fetch_failed = True
            continue

        for job in jobs:
            job["company"] = company["name"]
            job["notify_all"] = company.get("notify_all", False)
            unique_id = f"{company['name']}::{job['url']}"
            current_ids.add(unique_id)
            if unique_id not in seen_ids:
                new_jobs.append(job)

    # If any company failed to fetch this run, keep the roles we already saw so
    # a transient network blip doesn't wipe our memory and re-notify everything.
    if fetch_failed:
        current_ids |= seen_ids

    if not new_jobs:
        print(f"[{timestamp}] No new postings across {len(COMPANIES)} companies. {len(current_ids)} roles open in total.")
        save_seen_job_ids(current_ids)
        return

    for job in new_jobs:
        if job.get("notify_all"):
            # Alert on every posting; skip the AI filter (Ollama need not be up).
            is_relevant, status = True, "UNFILTERED"
        else:
            is_relevant, ai_available = check_relevance_with_ollama(job)
            status = "AI_UNAVAILABLE" if not ai_available else ("RELEVANT" if is_relevant else "FILTERED_OUT")
        log_every_new_job(job, status)

        print(f"[{timestamp}] NEW [{status}]: {job['company']} - {job['title']} ({job['location']})")

        if is_relevant:
            note = " (AI filter was down -- unfiltered)" if status == "AI_UNAVAILABLE" else ""
            title = f"{job['company']}: {job['title']}"
            message = f"{job['location']}{note}"
            send_mac_notification(title, message)
            send_android_push(title, f"{message}\n{job['url']}", url=job["url"])

    save_seen_job_ids(current_ids)


if __name__ == "__main__":
    main()

"""Offline tests for job_alert.py.

These run without network or Ollama. They feed representative API payloads
through the pure parse_* functions and check that each platform's distinct
JSON shape normalises into the common {title, location, url, description}
shape the rest of the pipeline relies on.

Run from the project root with:
    pytest
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import job_alert  # noqa: E402


def test_strip_html_removes_tags():
    assert job_alert.strip_html("<p>Hello <b>world</b></p>").strip() == "Hello  world"
    assert job_alert.strip_html(None) == ""


def test_parse_ashby():
    payload = {
        "jobs": [
            {
                "title": "Machine Learning Engineer",
                "location": "Remote - India",
                "jobUrl": "https://jobs.ashbyhq.com/atlan/abc",
                "descriptionPlain": "Build ML systems.",
            }
        ]
    }
    jobs = job_alert.parse_ashby_jobs(payload)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Machine Learning Engineer"
    assert jobs[0]["location"] == "Remote - India"
    assert jobs[0]["url"].endswith("abc")
    # common shape: exactly these four keys
    assert set(jobs[0]) == {"title", "location", "url", "description"}


def test_parse_greenhouse_handles_nested_location_and_html():
    payload = {
        "jobs": [
            {
                "title": "Computer Vision Engineer",
                "location": {"name": "Bengaluru"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                "content": "<p>Detection &amp; tracking.</p>",
            },
            {  # location can come back as null — must not crash
                "title": "Applied Scientist",
                "location": None,
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/2",
                "content": "Research role.",
            },
        ]
    }
    jobs = job_alert.parse_greenhouse_jobs(payload)
    assert jobs[0]["location"] == "Bengaluru"
    assert "<" not in jobs[0]["description"]  # HTML stripped
    assert jobs[1]["location"] == ""          # null location handled gracefully


def test_parse_lever_reads_top_level_list():
    payload = [
        {
            "text": "Data Scientist",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/acme/xyz",
            "descriptionPlain": "Modeling work.",
        }
    ]
    jobs = job_alert.parse_lever_jobs(payload)
    assert jobs[0]["title"] == "Data Scientist"
    assert jobs[0]["location"] == "Remote"
    assert jobs[0]["url"].endswith("xyz")


def test_all_parsers_emit_the_same_shape():
    """The core promise of the adapter pattern: one shape regardless of source."""
    ashby = job_alert.parse_ashby_jobs({"jobs": [{"title": "a", "jobUrl": "u"}]})[0]
    gh = job_alert.parse_greenhouse_jobs({"jobs": [{"title": "b", "absolute_url": "u"}]})[0]
    lever = job_alert.parse_lever_jobs([{"text": "c", "hostedUrl": "u"}])[0]
    keys = {"title", "location", "url", "description"}
    assert set(ashby) == set(gh) == set(lever) == keys

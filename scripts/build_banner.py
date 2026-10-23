"""Build assets/banner.svg for the GitHub profile.

Real data only:
  - number of tests: `pytest --collect-only -q` run on a checkout of the tests repo
  - CI status: latest GitHub Actions run of the tests repo (GitHub REST API)
If a value can't be read, the banner says so instead of guessing.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "banner.json").read_text(encoding="utf-8"))
OUT = ROOT / "assets" / "banner.svg"


def count_tests(repo_dir: Path):
    """Return the number of collected tests, or None if pytest can't collect."""
    if not repo_dir.is_dir():
        return None
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
             "-o", "addopts="],
            cwd=repo_dir, capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"(\d+) tests? collected", res.stdout)
    if m:
        return int(m.group(1))
    lines = [l for l in res.stdout.splitlines() if "::" in l]
    return len(lines) or None


def latest_ci_run(repo: str):
    """Return (conclusion, date) of the latest workflow run on main, or (None, None)."""
    url = f"https://api.github.com/repos/{repo}/actions/runs?branch=main&per_page=1"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            runs = json.load(r).get("workflow_runs", [])
    except Exception:
        return None, None
    if not runs:
        return None, None
    run = runs[0]
    status = run.get("conclusion") or run.get("status")
    when = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    return status, when


def fmt_date(d: datetime) -> str:
    return d.strftime("%d %b %Y")


def build_svg(tests, ci_status, ci_date, now) -> str:
    c = CONFIG
    green, red, amber, grey = "#3fb950", "#f85149", "#d29922", "#8b949e"

    if tests is None:
        test_txt, test_col = "tests: could not collect", amber
    else:
        test_txt, test_col = f"✔ {tests} tests collected", green

    if ci_status is None:
        ci_txt, ci_col = "CI status unavailable", amber
    elif ci_status == "success":
        ci_txt, ci_col = f"CI passed · {fmt_date(ci_date)}", green
    elif ci_status in ("failure", "cancelled", "timed_out"):
        ci_txt, ci_col = f"CI {ci_status} · {fmt_date(ci_date)}", red
    else:
        ci_txt, ci_col = f"CI {ci_status} · {fmt_date(ci_date)}", amber

    r = c["roadmap"]
    repo_short = c["tests_repo"].split("/")[-1]
    e = escape

    lines = [
        # (y, svg content, delay seconds)
        (62, f'<tspan fill="{green}">keller@github</tspan><tspan fill="{grey}">:~$ </tspan>whoami', 0.0),
        (100, f'<tspan class="name">{e(c["name"])}</tspan>', 0.4),
        (128, f'<tspan fill="#79c0ff">{e(c["title"])}</tspan>', 0.8),
        (168, f'<tspan fill="{green}">keller@github</tspan><tspan fill="{grey}">:~$ </tspan>pytest {e(repo_short)} --collect-only', 1.2),
        (192, f'<tspan fill="{test_col}">{e(test_txt)}</tspan><tspan fill="{grey}">   ·   </tspan><tspan fill="{ci_col}">{e(ci_txt)}</tspan>', 1.6),
        (232, f'<tspan fill="{green}">keller@github</tspan><tspan fill="{grey}">:~$ </tspan>cat roadmap.txt', 2.0),
        (256, f'<tspan fill="{grey}">now </tspan>{e(r["now"])}<tspan fill="{grey}">  ▸  next </tspan>{e(r["next"])}<tspan fill="{grey}">  ▸  then </tspan>{e(r["then"])}', 2.4),
    ]
    body = "\n".join(
        f'  <text x="32" y="{y}" class="ln" style="animation-delay:{d}s">{content}</text>'
        for y, content, d in lines
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="860" height="310" viewBox="0 0 860 310" role="img" aria-label="{e(c["name"])} — {e(c["title"])}. {e(test_txt)}, {e(ci_txt)}.">
  <style>
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 15px; fill: #e6edf3; }}
    .name {{ font-size: 30px; font-weight: 700; fill: #ffffff; }}
    .foot {{ font-size: 11px; fill: #6e7681; }}
    .ln {{ opacity: 0; animation: in .45s ease-out forwards; }}
    .cur {{ animation: blink 1s steps(1) infinite; }}
    @keyframes in {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .ln {{ opacity: 1; animation: none; }} .cur {{ animation: none; }} }}
  </style>
  <rect x="1" y="1" width="858" height="308" rx="12" fill="#0d1117" stroke="#30363d"/>
  <circle cx="24" cy="22" r="6" fill="#f85149"/><circle cx="44" cy="22" r="6" fill="#d29922"/><circle cx="64" cy="22" r="6" fill="#3fb950"/>
{body}
  <rect class="cur" x="32" y="272" width="9" height="17" fill="#e6edf3"/>
  <text x="828" y="294" text-anchor="end" class="foot">generated {fmt_date(now)} by a Python script · GitHub Actions</text>
</svg>
'''


def main():
    tests_dir = Path(os.environ.get("TESTS_DIR", ROOT / "_tests_repo"))
    tests = count_tests(tests_dir)
    ci_status, ci_date = latest_ci_run(CONFIG["tests_repo"])
    now = datetime.now(timezone.utc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_svg(tests, ci_status, ci_date, now), encoding="utf-8")
    print(f"tests={tests} ci={ci_status} date={ci_date} -> {OUT}")


if __name__ == "__main__":
    main()

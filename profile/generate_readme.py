#!/usr/bin/env python
"""
Generates JakeHildy's profile README (neofetch ASCII card) with LIVE stats.

Run by .github/workflows/stats.yml on a schedule. Stdlib only -- no pip install.
The art + static info are captured verbatim from the hand-tuned card; only the
GitHub Stats values (Repos / Stars / Commits / Followers / Lines of Code) are
computed each run, from the REST API:
  - /user + /user/repos                       -> repos, stars, followers
  - /repos/{repo}/stats/contributors         -> commits + LOC added/removed
    (walks every owned non-fork repo, sums this user's weekly a/d/c totals)

Auth: set ACCESS_TOKEN (classic PAT with `repo` + `read:user`) as a repo secret.
"""
import os
import json
import time
import urllib.request
import urllib.error

USERNAME = os.environ.get("GH_USERNAME", "JakeHildy")
TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
API = "https://api.github.com"
PAD = 47
TOTAL = 50  # leader-dot field width (matches the existing card)

# --- captured verbatim from the hand-tuned README -------------------------- #
LEFT = [ "                  \\   |   /", "                ---   .-.   ---", "                     ( O )", "                ---   `-'   ---", "                  /   |   \\", "         /\\                         /\\", "        /  \\         /\\            /  \\", "       / /\\ \\       /  \\    /\\    / /\\ \\", "      / /  \\ \\     / /\\ \\  /  \\  / /  \\ \\", "     /_/    \\_\\   /_/  \\_\\/ /\\ \\/_/    \\_\\", "    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", "                               __o", "                             _ \\<,_", "                            (_)/ (_)", "", "    ╭──────────────────────────────────────╮", "    │  o o o           ~/zebel -- zsh      │", "    ├──────────────────────────────────────┤", "    │  $ npm run startup                   │", "    │  > api   ready on :5002              │", "    │  > ui    ready on :3000              │", "    │  > prisma       16 models synced     │", "    │                                      │", "    │  $ git commit -m \"ship it\"           │", "    │  [##############----]  74%           │", "    │  > _                                 │", "    ╰──────────────────────────────────────╯" ]

STATIC_INFO = [ "Jacob Hildebrandt ----------------------------------", "", "- OS ......................... macOS (Apple Silicon)", "- Uptime .................................. 34 years", "- Host ................................. Zebel, Inc.", "- Kernel ......................... Software Engineer", "- Shell ........................................ zsh", "- IDE ......................... Claude Code, VS Code", "", "- Languages ............ JavaScript, C#, Python, SQL", "- Stack.Backend ........ Fastify, Prisma, PostgreSQL", "- Stack.Frontend ..... React 19, Vite, Tailwind, SWR", "", "- Hobbies.Software ................... Side projects", "- Hobbies.Outdoors ................. Mountain biking", "- Hobbies.Reading ..................... Sci-fi books", "", "- Contact --------------------------------------------", "- Email .............................. jake@zebel.io", "- GitHub ................................ @JakeHildy", "", "- GitHub Stats ---------------------------------------" ]

# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
def _open(url):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": USERNAME + "-profile-stats"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=45)

def get_json(url, retries=6):
    for attempt in range(retries):
        try:
            resp = _open(url)
        except urllib.error.HTTPError as e:
            if e.code == 202:
                time.sleep(2 * (attempt + 1)); continue
            raise
        if resp.status == 202:
            time.sleep(2 * (attempt + 1)); continue
        return json.loads(resp.read().decode()), resp.headers.get("Link", "")
    return None, ""

def get_all(url):
    items = []
    while url:
        data, link = get_json(url)
        if not isinstance(data, list):
            break
        items.extend(data)
        url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                url = part[part.find("<") + 1: part.find(">")]
    return items

# --------------------------------------------------------------------------- #
# Stat collection
# --------------------------------------------------------------------------- #
def fetch_user():
    data, _ = get_json(API + ("/user" if TOKEN else "/users/" + USERNAME))
    return data or {}

def fetch_repos():
    if TOKEN:
        return get_all(API + "/user/repos?affiliation=owner&per_page=100&sort=pushed")
    return get_all(API + "/users/" + USERNAME + "/repos?per_page=100&sort=pushed")

def repo_totals(full_name):
    data, _ = get_json(API + "/repos/" + full_name + "/stats/contributors")
    a = d = c = 0
    if isinstance(data, list):
        for contrib in data:
            author = contrib.get("author") or {}
            if author.get("login", "").lower() == USERNAME.lower():
                for wk in contrib.get("weeks", []):
                    a += wk.get("a", 0); d += wk.get("d", 0); c += wk.get("c", 0)
    return a, d, c

def collect_stats():
    user = fetch_user()
    repos = fetch_repos()
    own = [r for r in repos if not r.get("fork")]
    stars = sum(r.get("stargazers_count", 0) for r in own)
    add = dele = commits = 0
    for r in own:
        a, d, c = repo_totals(r["full_name"])
        add += a; dele += d; commits += c
    return {
        "repos": len(own), "stars": stars,
        "followers": user.get("followers", 0), "following": user.get("following", 0),
        "commits": commits, "loc": add - dele, "loc_add": add, "loc_del": dele,
    }

# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def dots(label, value, total=TOTAL):
    fill = max(1, total - len(label) - len(value))
    return label + " " + "." * fill + " " + value

def render(stats):
    n = lambda v: format(v, ",")
    stat_lines = [
        dots("- Repos", n(stats["repos"]) + "  |  Stars: " + n(stats["stars"])),
        dots("- Commits", n(stats["commits"])),
        dots("- Followers", n(stats["followers"]) + "  |  Following: " + n(stats["following"])),
        dots("- Lines of Code", n(stats["loc"])),
        dots("-   +/-", n(stats["loc_add"]) + "++ / " + n(stats["loc_del"]) + "--"),
        dots("- Member Since", "2020"),
    ]
    info = STATIC_INFO + stat_lines
    rows = max(len(LEFT), len(info))
    out = []
    for i in range(rows):
        left = LEFT[i] if i < len(LEFT) else ""
        right = info[i] if i < len(info) else ""
        out.append((left.ljust(PAD) + right).rstrip())
    return "\n".join(out)

def write_readme(block):
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, "README.md")
    with open(path, "w") as f:
        f.write("```text\n" + block + "\n```\n")
    print("wrote " + path + " (" + str(len(block.splitlines())) + " lines)")

if __name__ == "__main__":
    if os.environ.get("MOCK") == "1":
        stats = {"repos": 78, "stars": 3, "followers": 17, "following": 18,
                 "commits": 2116, "loc": 446276, "loc_add": 523178, "loc_del": 76902}
    else:
        stats = collect_stats()
    print(json.dumps(stats))
    write_readme(render(stats))

#!/usr/bin/env python3
"""
generate_svgs.py
Fetches live GitHub data for MilindTajane143 and regenerates:
  - milind-stats.svg
  - milind-langs.svg
  - milind-trophies.svg
Run by GitHub Actions daily.
"""

import os, sys, json, math, urllib.request, urllib.error

USERNAME  = "MilindTajane143"
TOKEN     = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR   = os.environ.get("OUT_DIR", ".")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "milind-profile-bot/1.0",
}

# ─── helpers ──────────────────────────────────────────────────────────────────
def gh_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} for {url}", file=sys.stderr)
        return {}

def gh_graphql(query):
    data = json.dumps({"query": query}).encode()
    req  = urllib.request.Request(
        "https://api.github.com/graphql",
        data=data, headers={**HEADERS, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()).get("data", {})
    except Exception as e:
        print(f"GraphQL error: {e}", file=sys.stderr)
        return {}

# ─── fetch data ───────────────────────────────────────────────────────────────
def fetch_all():
    print("Fetching user info…")
    user = gh_get(f"https://api.github.com/users/{USERNAME}")

    print("Fetching repos…")
    repos, page = [], 1
    while True:
        page_data = gh_get(
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner"
        )
        if not page_data:
            break
        repos.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1

    # Stars
    stars = sum(r.get("stargazers_count", 0) for r in repos)

    # Language bytes
    lang_bytes = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        lang = repo.get("language")
        if lang:
            lang_bytes[lang] = lang_bytes.get(lang, 0) + repo.get("size", 1)

    # Sort and keep top 6
    top_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:6]
    total_bytes = sum(v for _, v in top_langs) or 1
    lang_pcts = [(l, round(v * 100 / total_bytes, 1)) for l, v in top_langs]

    # Commits + PRs + Issues via GraphQL
    print("Fetching commits / PRs / issues via GraphQL…")
    gql_result = gh_graphql(f"""
    {{
      user(login: "{USERNAME}") {{
        contributionsCollection {{
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          contributionCalendar {{
            totalContributions
          }}
        }}
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, REVIEW]) {{
          totalCount
        }}
        pullRequests(states: MERGED) {{ totalCount }}
        issues(states: CLOSED)     {{ totalCount }}
        followers {{ totalCount }}
      }}
    }}
    """)

    contrib = (gql_result.get("user") or {}).get("contributionsCollection") or {}
    gql_user = gql_result.get("user") or {}

    commits    = contrib.get("totalCommitContributions", 0)
    prs        = (gql_user.get("pullRequests") or {}).get("totalCount", 0)
    issues     = (gql_user.get("issues") or {}).get("totalCount", 0)
    followers  = (gql_user.get("followers") or {}).get("totalCount",
                  user.get("followers", 0))
    pub_repos  = user.get("public_repos", len(repos))
    contrib_to = (gql_user.get("repositoriesContributedTo") or {}).get("totalCount", 0)
    total_contrib = (contrib.get("contributionCalendar") or {}).get("totalContributions", commits)

    # Compute rank (simple formula similar to github-readme-stats)
    score = (
        commits * 0.2
        + prs * 0.5
        + issues * 0.3
        + stars * 1.5
        + followers * 0.45
        + pub_repos * 0.2
        + contrib_to * 0.5
    )
    if   score >= 400: rank = "S+"
    elif score >= 300: rank = "S"
    elif score >= 200: rank = "A+"
    elif score >= 120: rank = "A"
    elif score >= 60:  rank = "B+"
    elif score >= 30:  rank = "B"
    else:              rank = "C"

    return dict(
        username=USERNAME,
        stars=stars,
        commits=commits,
        prs=prs,
        issues=issues,
        pub_repos=pub_repos,
        contrib_to=contrib_to,
        followers=followers,
        total_contrib=total_contrib,
        rank=rank,
        lang_pcts=lang_pcts,
    )

# ─── SVG generators ───────────────────────────────────────────────────────────
LANG_COLORS = {
    "JavaScript": "#f7df1e", "TypeScript": "#3178c6", "Python": "#3572a5",
    "Java": "#b07219",       "Go": "#00add8",           "Rust": "#dea584",
    "C++": "#f34b7d",        "C": "#555555",            "C#": "#178600",
    "HTML": "#e34c26",       "CSS": "#563d7c",           "SCSS": "#c6538c",
    "Vue": "#41b883",        "React": "#61dafb",         "Shell": "#89e051",
    "Ruby": "#701516",       "PHP": "#4f5d95",           "Kotlin": "#7f52ff",
    "Swift": "#fa7343",      "Dart": "#00b4ab",          "Markdown": "#083fa1",
}
def lang_color(name):
    return LANG_COLORS.get(name, "#bf5af2")

# ── stats SVG ──────────────────────────────────────────────────────────────────
def make_stats_svg(d):
    rank = d["rank"]
    # ring fill: % of arc = (score up to S+ mapped to 0-100)
    rank_map = {"S+":98,"S":88,"A+":76,"A":62,"B+":48,"B":34,"C":18}
    fill_pct = rank_map.get(rank, 50) / 100
    # circumference of r=52 circle
    circum = 2 * math.pi * 52          # ≈ 326.7
    dasharray  = round(circum * fill_pct, 1)
    dashoffset = round(circum, 1)

    rows = [
        ("⭐", "Total Stars Earned:",      str(d["stars"]),      "#fde047"),
        ("💻", "Total Commits (2024):",    str(d["commits"]),    "#7dd3fc"),
        ("🔀", "Total PRs:",               str(d["prs"]),        "#4ade80"),
        ("🐛", "Total Issues Closed:",     str(d["issues"]),     "#fb923c"),
        ("📦", "Public Repos:",            str(d["pub_repos"]),  "#c084fc"),
        ("⚡", "Total Contributions:",     str(d["total_contrib"]),"#ff4da6"),
    ]

    row_svgs = ""
    for i, (icon, label, val, color) in enumerate(rows):
        delay = 0.50 + i * 0.22
        y = 74 + i * 31
        row_svgs += f"""
  <g class="row" style="animation-delay:{delay:.2f}s">
    <text x="24" y="{y}" font-size="14">{icon}</text>
    <text x="52" y="{y}" font-size="13.5" fill="#c9d1d9">{label}</text>
    <text x="316" y="{y}" text-anchor="end" font-size="14" font-weight="bold" fill="{color}">{val}</text>
  </g>"""

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 232" width="500" height="232" role="img" aria-label="Milind Tajane's GitHub stats">
<defs><style><![CDATA[
text{{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace}}
@keyframes fadeSlide{{from{{opacity:0;transform:translateX(-14px)}}to{{opacity:1;transform:translateX(0)}}}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes rankPulse{{0%,100%{{opacity:.85}}50%{{opacity:1}}}}
@keyframes shineX{{0%{{transform:translateX(-160px) skewX(-15deg)}}60%,100%{{transform:translateX(560px) skewX(-15deg)}}}}
.row{{opacity:0;animation:fadeSlide .5s ease forwards}}
.rk{{animation:rankPulse 2.4s ease-in-out infinite}}
.sh{{animation:shineX 4.5s ease-in-out 2.4s infinite}}
]]></style>
<linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0%"><animate attributeName="stop-color" values="#ff4da6;#bf5af2;#ff4da6" dur="6s" repeatCount="indefinite"/></stop>
  <stop offset="100%"><animate attributeName="stop-color" values="#bf5af2;#ff4da6;#bf5af2" dur="6s" repeatCount="indefinite"/></stop>
</linearGradient>
<linearGradient id="ringg" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0%" stop-color="#ff4da6"/><stop offset="100%" stop-color="#8b5cf6"/>
</linearGradient>
<linearGradient id="shg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#fff" stop-opacity="0"/><stop offset="50%" stop-color="#fff" stop-opacity=".07"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="cc"><rect x="1" y="1" width="498" height="230" rx="14"/></clipPath>
<filter id="g"><feGaussianBlur stdDeviation="2" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect x="1" y="1" width="498" height="230" rx="14" fill="#170e28" stroke="url(#tg)" stroke-width="1.5"/>
<text x="24" y="38" font-size="16" font-weight="bold" fill="url(#tg)">📊 Milind Tajane's GitHub Stats</text>
{row_svgs}
<!-- Rank ring -->
<g transform="translate(422,138)">
  <circle r="52" fill="none" stroke="#241740" stroke-width="9"/>
  <circle r="52" fill="none" stroke="url(#ringg)" stroke-width="9" stroke-linecap="round"
    stroke-dasharray="{dasharray} {dashoffset}" stroke-dashoffset="{dashoffset}" transform="rotate(-90)">
    <animate attributeName="stroke-dashoffset" from="{dashoffset}" to="0" dur="1.6s" begin=".6s" fill="freeze" calcMode="spline" keySplines=".2 .8 .3 1"/>
  </circle>
  <text class="rk" y="14" text-anchor="middle" font-size="32" font-weight="bold" fill="#ff4da6" filter="url(#g)">{rank}</text>
  <text y="76" text-anchor="middle" font-size="10.5" fill="#8b949e" opacity="0" style="animation:fadeIn .5s ease 1.8s forwards">RANK</text>
</g>
<g clip-path="url(#cc)"><rect class="sh" x="0" y="0" width="120" height="232" fill="url(#shg)"/></g>
</svg>"""

# ── langs SVG ──────────────────────────────────────────────────────────────────
def make_langs_svg(d):
    langs = d["lang_pcts"]  # [(name, pct), …]
    if not langs:
        langs = [("JavaScript", 100.0)]
    total = sum(p for _, p in langs) or 1

    # stacked top bar segments
    bar_x = 20.0
    bar_width = 380.0
    segments = ""
    for name, pct in langs:
        w = round(bar_width * pct / total, 1)
        segments += f'<rect x="{bar_x:.1f}" y="58" width="{w}" height="11" fill="{lang_color(name)}"/>\n'
        bar_x += w

    # row items
    rows_svg = ""
    row_ys   = [91, 133, 175, 217, 255, 293]
    bar_ys   = [99, 141, 183, 225, 263, 301]
    for i, (name, pct) in enumerate(langs[:6]):
        delay1 = 0.90 + i * 0.35
        delay2 = delay1 + 0.15
        color  = lang_color(name)
        ry     = row_ys[i]
        by     = bar_ys[i]
        bar_w  = round(268 * pct / total, 1)
        rows_svg += f"""
  <g class="row" style="animation-delay:{delay1:.2f}s">
    <circle cx="26" cy="{ry}" r="5" fill="{color}"/>
    <text x="40" y="{ry+5}" font-size="13" fill="#e6edf3" font-weight="bold">{name}</text>
    <text x="396" y="{ry+5}" text-anchor="end" font-size="13" fill="{color}" font-weight="bold">{pct}%</text>
    <rect x="40" y="{by}" width="268" height="9" rx="4.5" fill="#241740"/>
    <rect x="40" y="{by}" width="0" height="9" rx="4.5" fill="{color}" style="animation-delay:{delay2:.2f}s">
      <animate attributeName="width" from="0" to="{bar_w}" dur="1.1s" begin="{delay2:.2f}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .3 1"/>
    </rect>
  </g>"""

    height = 80 + len(langs[:6]) * 42
    clip_h = height - 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 {height}" width="420" height="{height}" role="img" aria-label="Top languages">
<defs><style><![CDATA[
text{{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace}}
@keyframes fadeUp{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes shineX{{0%{{transform:translateX(-140px)}}60%,100%{{transform:translateX(460px)}}}}
.row{{opacity:0;animation:fadeUp .5s ease forwards}}
.sh{{animation:shineX 4s ease-in-out 2.2s infinite}}
]]></style>
<linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0%"><animate attributeName="stop-color" values="#ff4da6;#bf5af2;#ff4da6" dur="6s" repeatCount="indefinite"/></stop>
  <stop offset="100%"><animate attributeName="stop-color" values="#bf5af2;#ff4da6;#bf5af2" dur="6s" repeatCount="indefinite"/></stop>
</linearGradient>
<linearGradient id="shg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#fff" stop-opacity="0"/><stop offset="50%" stop-color="#fff" stop-opacity=".08"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="cardc"><rect x="1" y="1" width="418" height="{clip_h}" rx="14"/></clipPath>
<clipPath id="stackc"><rect x="20" y="58" width="0" height="11" rx="5.5"><animate attributeName="width" from="0" to="380" dur="1.4s" begin=".4s" fill="freeze" calcMode="spline" keySplines=".2 .8 .3 1"/></rect></clipPath>
</defs>
<rect x="1" y="1" width="418" height="{clip_h}" rx="14" fill="#170e28" stroke="url(#tg)" stroke-width="1.5"/>
<text x="20" y="34" font-size="16" font-weight="bold" fill="url(#tg)">💻 Top Languages</text>
<g clip-path="url(#stackc)">{segments}</g>
{rows_svg}
<g clip-path="url(#cardc)"><rect class="sh" x="0" y="0" width="100" height="{height}" fill="url(#shg)" transform="skewX(-15)"/></g>
</svg>"""

# ── trophies SVG ───────────────────────────────────────────────────────────────
def make_trophies_svg(d):
    cells = [
        ("🚀", "Fullstack Dev",     f"React+Node x{d['pub_repos']}",  d["rank"],     "#ff4da6"),
        ("🌟", "Starstruck",        f"Stars {d['stars']}+",           "S"  if d["stars"]   >= 50  else "B", "#fde047"),
        ("🔥", "Committer",         f"Commits {d['commits']}+",       "A+" if d["commits"] >= 200 else "B", "#e040fb"),
        ("💜", "Rising Star",       f"Followers {d['followers']}+",   "A"  if d["followers"] >= 10 else "B","#bf5af2"),
        ("🔀", "PR Master",         f"PRs {d['prs']}+",               "A"  if d["prs"]     >= 20  else "B", "#7dd3fc"),
        ("📦", "Creator",           f"Repos {d['pub_repos']}+",       "B"  if d["pub_repos"] >= 5  else "C", "#4ade80"),
    ]
    cells_svg = ""
    for i, (emoji, title, sub, rk, color) in enumerate(cells):
        x      = 12 + i * 180
        cx     = x + 84
        end_x  = x + 156
        delay  = 0.30 + i * 0.18
        d2     = delay + 0.40
        cells_svg += f"""
  <g class="cell" style="animation-delay:{delay:.2f}s">
    <rect x="{x}" y="12" width="168" height="144" rx="14" fill="#170e28" stroke="{color}" stroke-opacity=".55" stroke-width="1.3"/>
    <text x="{cx}" y="52" text-anchor="middle" font-size="30">{emoji}</text>
    <text class="rk" x="{end_x}" y="40" text-anchor="end" font-size="24" font-weight="bold" fill="{color}" style="animation-delay:{d2:.2f}s">{rk}</text>
    <text x="{cx}" y="90" text-anchor="middle" font-size="14" font-weight="bold" fill="#e6edf3">{title}</text>
    <text x="{cx}" y="112" text-anchor="middle" font-size="11" fill="#9aa4b2">{sub}</text>
    <rect x="{x+18}" y="124" width="132" height="5" rx="2.5" fill="#241740"/>
    <rect x="{x+18}" y="124" width="0" height="5" rx="2.5" fill="{color}">
      <animate attributeName="width" from="0" to="132" dur="1s" begin="{d2:.2f}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .3 1"/>
    </rect>
  </g>"""

    total_w = 12 + len(cells) * 180
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} 168" width="{total_w}" height="168" role="img" aria-label="GitHub trophies">
<defs><style><![CDATA[
text{{font-family:'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace}}
@keyframes popCell{{0%{{opacity:0;transform:translateY(16px) scale(.85)}}70%{{opacity:1;transform:translateY(-3px) scale(1.03)}}100%{{opacity:1;transform:translateY(0) scale(1)}}}}
@keyframes rankGlow{{0%,100%{{opacity:.75}}50%{{opacity:1}}}}
@keyframes shineX2{{0%{{transform:translateX(-200px) skewX(-15deg)}}60%,100%{{transform:translateX({total_w+200}px) skewX(-15deg)}}}}
.cell{{opacity:0;animation:popCell .55s cubic-bezier(.2,.8,.3,1.2) forwards;transform-box:fill-box;transform-origin:center}}
.rk{{animation:rankGlow 2.2s ease-in-out infinite}}
.sh2{{animation:shineX2 5s ease-in-out 2s infinite}}
]]></style>
<linearGradient id="shg2" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#fff" stop-opacity="0"/><stop offset="50%" stop-color="#fff" stop-opacity=".07"/><stop offset="100%" stop-color="#fff" stop-opacity="0"/></linearGradient>
<clipPath id="tc"><rect x="0" y="0" width="{total_w}" height="168" rx="14"/></clipPath>
</defs>
{cells_svg}
<g clip-path="url(#tc)"><rect class="sh2" x="0" y="0" width="140" height="168" fill="url(#shg2)"/></g>
</svg>"""

# ─── main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    data = fetch_all()
    print(f"\n✅ Fetched data for {USERNAME}:")
    print(json.dumps({k: v for k, v in data.items() if k != "lang_pcts"}, indent=2))
    print("Languages:", data["lang_pcts"])

    os.makedirs(OUT_DIR, exist_ok=True)

    stats_path    = os.path.join(OUT_DIR, "milind-stats.svg")
    langs_path    = os.path.join(OUT_DIR, "milind-langs.svg")
    trophies_path = os.path.join(OUT_DIR, "milind-trophies.svg")

    with open(stats_path,    "w") as f: f.write(make_stats_svg(data))
    with open(langs_path,    "w") as f: f.write(make_langs_svg(data))
    with open(trophies_path, "w") as f: f.write(make_trophies_svg(data))

    print(f"\n✅ Written:")
    print(f"   {stats_path}")
    print(f"   {langs_path}")
    print(f"   {trophies_path}")

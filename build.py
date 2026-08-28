#!/usr/bin/env python3
"""Build the framework-free Security Slayer site from the existing Markdown."""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "public"


def frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    raw, body = text[4:].split("\n---\n", 1)
    data: dict[str, object] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line:
            i += 1
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if not value:
            items: list[str] = []
            i += 1
            while i < len(lines) and lines[i].startswith("  - "):
                items.append(lines[i][4:].strip().strip('"\''))
                i += 1
            data[key] = items
            continue
        if value.startswith("["):
            data[key] = json.loads(value.replace("'", '"'))
        elif value.lower() in ("true", "false"):
            data[key] = value.lower() == "true"
        else:
            data[key] = value.strip('"\'')
        i += 1
    return data, body


def render_markdown(markdown: str) -> str:
    result = subprocess.run(
        ["pandoc", "--from=gfm", "--to=html5", "--wrap=none"],
        input=markdown,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def display_date(value: object) -> str:
    raw = str(value).split("T")[0]
    return datetime.strptime(raw, "%Y-%m-%d").strftime("%d %b %Y").upper()


def reading_time(body: str) -> int:
    words = len(re.findall(r"\b\w+\b", body))
    return max(1, round(words / 210))


def nav(active: str) -> str:
    links = [("HOME", "/"), ("POSTS", "/posts/"), ("TAGS", "/tags/"), ("ABOUT", "/about/")]
    return "".join(
        f'<a href="{url}"{(" class=\"active\"" if label == active else "")}'
        f'><span>0{i}</span>{label}</a>' for i, (label, url) in enumerate(links, 1)
    )


def shell(title: str, content: str, active: str, description: str = "Cybersecurity field notes by Aibel") -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#070a08">
  <meta name="description" content="{esc(description)}">
  <title>{esc(title)} // Security Slayer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/css/main.css">
  <script src="/js/main.js" defer></script>
</head>
<body>
  <div class="noise" aria-hidden="true"></div>
  <div class="loader" aria-label="Initializing site">
    <div class="loader-core"><img class="loader-mark" src="/images/alt.png" alt=""><p>INITIALIZING SECURE UPLINK</p><div class="loader-track"><i></i></div><small>SYS.BOOT / <b>00</b>%</small></div>
  </div>
  <header class="site-header">
    <a class="brand" href="/" aria-label="Security Slayer home"><i></i><span>AIBEL</span><b>//SEC</b></a>
    <nav>{nav(active)}</nav>
    <button class="nav-toggle" aria-label="Toggle navigation" aria-expanded="false"><i></i><i></i></button>
  </header>
  <main>{content}</main>
  <footer><div><span>AIBEL // SECURITY SLAYER</span><small>OFFENSIVE SECURITY · FIELD NOTES · 2026</small></div><p><i></i> SYSTEM ONLINE</p><div class="footer-links"><a href="https://github.com/AibelKingslayer" aria-label="GitHub"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.1.79-.25.79-.56v-2.23c-3.23.7-3.91-1.37-3.91-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.7.08-.7 1.16.08 1.78 1.2 1.78 1.2 1.04 1.77 2.71 1.26 3.37.96.1-.75.4-1.26.74-1.55-2.58-.29-5.29-1.29-5.29-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.47.11-3.06 0 0 .97-.31 3.16 1.18a10.9 10.9 0 0 1 5.76 0c2.19-1.49 3.16-1.18 3.16-1.18.63 1.59.23 2.77.11 3.06.74.81 1.19 1.84 1.19 3.1 0 4.42-2.72 5.4-5.3 5.69.42.36.79 1.06.79 2.14v3.18c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z"/></svg><span>GITHUB</span></a><a href="https://linkedin.com/in/aibel-aju" aria-label="LinkedIn"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5.37 7.98H1.72V22h3.65V7.98ZM3.55 2A2.12 2.12 0 1 0 3.55 6.24 2.12 2.12 0 0 0 3.55 2ZM22.28 14.12c0-4.22-2.25-6.18-5.25-6.18-2.42 0-3.5 1.33-4.1 2.27V7.98H9.28V22h3.65v-6.94c0-1.83.35-3.61 2.63-3.61 2.25 0 2.28 2.1 2.28 3.73V22h3.65l.79-7.88Z"/></svg><span>LINKEDIN</span></a></div></footer>
  <div class="cursor-dot" aria-hidden="true"></div>
</body>
</html>'''


def post_card(post: dict[str, object], index: int) -> str:
    tags = post["tags"]
    tag_html = "".join(f'<a href="/tags/#{esc(t).lower()}">{esc(t)}</a>' for t in tags[:3])
    return f'''<article class="post-card reveal" data-tags="{' '.join(str(t).lower() for t in tags)}">
      <div class="card-index">{index:02d}<span>/0{len(POSTS)}</span></div>
      <div class="card-body"><div class="eyebrow">{display_date(post['date'])} <i></i> {post['minutes']} MIN READ</div>
      <h2><a href="/posts/{post['slug']}/">{esc(post['title'])}</a></h2>
      <p>{esc(post['description'])}</p><div class="card-foot"><div class="tags">{tag_html}</div><a class="open" href="/posts/{post['slug']}/">OPEN FILE <span>↗</span></a></div></div>
    </article>'''


POSTS: list[dict[str, object]] = []
for path in CONTENT.glob("posts/*.md"):
    meta, body = frontmatter(path)
    if meta.get("draft") is True:
        continue
    meta.update(slug=path.stem, body=body, minutes=reading_time(body))
    POSTS.append(meta)
POSTS.sort(key=lambda p: str(p["date"]), reverse=True)


def build() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir()
    shutil.copytree(ASSETS / "css", OUTPUT / "css")
    shutil.copytree(ASSETS / "js", OUTPUT / "js")
    if (ROOT / "static" / "images").exists():
        shutil.copytree(ROOT / "static" / "images", OUTPUT / "images")
    (OUTPUT / "images").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "alt.png", OUTPUT / "images" / "alt.png")

    cards = "".join(post_card(p, i) for i, p in enumerate(POSTS, 1))
    latest = POSTS[0]
    home = f'''<section class="hero">
      <div class="hero-grid"></div><div class="hero-copy reveal"><div class="kicker"><span>ROOT@AIBEL:~$</span> WHOAMI</div>
      <h1>BREAK.<br><span>LEARN.</span><br>DOCUMENT.</h1>
      <p>Offensive security field notes from the edge of the network. Penetration testing, adversary simulation, and the lessons found between access and root.</p>
      <div class="hero-actions"><a class="button primary" href="/posts/">EXPLORE INTEL <span>→</span></a><a class="button ghost" href="/about/">IDENTIFY OPERATOR</a></div></div>
      <aside class="hud reveal"><div class="hud-top"><span>OPERATOR_PROFILE</span><i>LIVE</i></div><div class="portrait"><img src="/images/alt.png" alt="Aibel profile insignia"><span class="corner c1"></span><span class="corner c2"></span><span class="corner c3"></span><span class="corner c4"></span></div><dl><div><dt>HANDLE</dt><dd>AIBEL</dd></div><div><dt>ROLE</dt><dd>OFFSEC</dd></div><div><dt>STATUS</dt><dd class="green">ACTIVE</dd></div><div><dt>CERT</dt><dd>OSCP+</dd></div></dl><div class="signal"><i></i><i></i><i></i><i></i><i></i><span>UPLINK 98.7%</span></div></aside>
      <div class="scroll-cue">SCROLL TO DECRYPT <i></i></div>
    </section>
    <section class="ticker"><span>THREAT INTELLIGENCE</span><div><p>RED TEAM OPERATIONS · ACTIVE DIRECTORY · WEB EXPLOITATION · WINDOWS INTERNALS · AUTOMATION · <b>KNOWLEDGE IS THE PAYLOAD</b>&nbsp; · RED TEAM OPERATIONS · ACTIVE DIRECTORY · WEB EXPLOITATION · WINDOWS INTERNALS · AUTOMATION ·&nbsp;</p></div></section>
    <section class="section posts-preview"><div class="section-head reveal"><div><span class="section-no">01 //</span><h2>LATEST<br>INTEL</h2></div><p>FIELD REPORTS, TECHNIQUES,<br>AND OPERATIONAL NOTES.</p><a href="/posts/">VIEW ALL FILES ↗</a></div>{cards[:cards.find('</article>')+10]}</section>
    <section class="featured reveal"><span>NEWEST TRANSMISSION</span><div><h2>{esc(latest['title'])}</h2><p>{esc(latest['description'])}</p><a href="/posts/{latest['slug']}/">READ TRANSMISSION →</a></div><b>0{len(POSTS)}</b></section>'''
    (OUTPUT / "index.html").write_text(shell("Home", home, "HOME"), encoding="utf-8")

    posts_page = f'''<section class="page-hero reveal"><div class="kicker"><span>DIR://</span> FIELD_NOTES</div><h1>ALL <span>INTEL.</span></h1><p>{len(POSTS):02d} decrypted transmissions. Practical notes from the offensive security field.</p></section><section class="section archive"><div class="archive-bar"><span>INDEX / DESCENDING</span><label>FILTER <input id="post-filter" type="search" placeholder="TYPE TO SEARCH_" autocomplete="off"></label></div><div id="post-list">{cards}</div></section>'''
    out = OUTPUT / "posts"; out.mkdir()
    (out / "index.html").write_text(shell("Posts", posts_page, "POSTS"), encoding="utf-8")

    for i, post in enumerate(POSTS, 1):
        tag_html = "".join(f'<a href="/tags/#{esc(t).lower()}">{esc(t)}</a>' for t in post["tags"])
        article = f'''<article class="article"><header class="article-head reveal"><a class="back" href="/posts/">← RETURN TO INDEX</a><div class="eyebrow">FILE 0{i} / {display_date(post['date'])}</div><h1>{esc(post['title'])}</h1><p>{esc(post['description'])}</p><div class="article-meta"><span>AUTHOR // {esc(post.get('author', 'Aibel'))}</span><span>READ_TIME // {post['minutes']} MIN</span></div><div class="tags">{tag_html}</div></header><div class="article-layout"><aside class="toc"><span>ON THIS PAGE</span><nav></nav></aside><div class="prose">{render_markdown(str(post['body']))}</div><aside class="rail"><span>READ PROGRESS</span><b>00%</b><i></i></aside></div></article>'''
        folder = OUTPUT / "posts" / str(post["slug"]); folder.mkdir()
        (folder / "index.html").write_text(shell(str(post["title"]), article, "POSTS", str(post["description"])), encoding="utf-8")

    about_meta, about_body = frontmatter(CONTENT / "about.md")
    about = f'''<section class="page-hero about-hero reveal"><div class="kicker"><span>ROOT@AIBEL:~$</span> ABOUT</div><h1>THE HUMAN<br><span>BEHIND THE HANDLE.</span></h1><div class="identity"><img src="/images/alt.png" alt="Aibel profile insignia"><p>OFFENSIVE SECURITY<br>OPERATOR / RESEARCHER<br><i>INDIA · UTC+05:30</i></p></div></section><section class="article-layout about-layout"><aside class="toc"><span>IDENTITY FILE</span><nav></nav></aside><div class="prose reveal">{render_markdown(about_body)}</div><aside class="rail"><span>CLEARANCE</span><b>ROOT</b><i></i></aside></section>'''
    out = OUTPUT / "about"; out.mkdir(); (out / "index.html").write_text(shell("About", about, "ABOUT", str(about_meta.get("summary", "About Aibel"))), encoding="utf-8")

    all_tags = sorted({str(t) for p in POSTS for t in p["tags"]}, key=str.lower)
    chips = "".join(f'<button data-tag="{esc(t).lower()}"><span>#</span>{esc(t)}</button>' for t in all_tags)
    tags_page = f'''<section class="page-hero reveal"><div class="kicker"><span>CAT://</span> TAXONOMY</div><h1>SIGNAL <span>TAGS.</span></h1><p>Filter the intelligence archive by operational domain.</p></section><section class="section tag-browser"><div class="tag-cloud">{chips}</div><div id="tag-results">{cards}</div></section>'''
    out = OUTPUT / "tags"; out.mkdir(); (out / "index.html").write_text(shell("Tags", tags_page, "TAGS"), encoding="utf-8")

    (OUTPUT / "404.html").write_text(shell("404", '<section class="not-found"><span>ERROR // 404</span><h1>SIGNAL<br>LOST.</h1><p>The requested node does not exist or has gone dark.</p><a class="button primary" href="/">RETURN TO BASE →</a></section>', ""), encoding="utf-8")
    (OUTPUT / ".nojekyll").touch()


if __name__ == "__main__":
    build()

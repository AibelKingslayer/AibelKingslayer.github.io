# Security Slayer

A framework-free static cybersecurity blog built from the Markdown files in `content/`.

## Build locally

Pandoc 2.9+ and Python 3 are required.

```bash
python3 build.py
python3 -m http.server 4173 --directory public
```

Open `http://localhost:4173`. GitHub Actions runs the same build and deploys the generated `public/` directory to GitHub Pages.

## Structure

- `content/` — articles and profile content
- `assets/` — site CSS and JavaScript
- `static/images/` — article images
- `build.py` — static-site generator

There is no runtime framework, package manager, or client-side content dependency.

# Talent Angels — Skill Graph Analyzer

**Part of the [Learning Tokens](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/80) project · Linux Foundation Mentorship 2026**

Upload a CV and get an instant map of your skills, knowledge gaps, and a personalized learning path — all powered by AI agents and knowledge graph theory.

---

## What it does

1. **Locator agent** — reads your CV (PDF or DOCX) and identifies your skills by matching them semantically to global taxonomies (ESCO, O\*NET, SFIA).
2. **Connector agent** — for each skill found, maps adjacent nodes in the knowledge graph: what you needed to learn it and what it unlocks next.
3. **Pathfinder agent** — computes the shortest path in the graph from your current skills to recommended next skills.
4. **Learning plan** — Claude synthesizes everything into a concrete, phased learning roadmap.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 · Flask · Gunicorn |
| AI / LLM | Anthropic Claude (`claude-sonnet-4`) |
| Graph engine | NetworkX (directed graph, BFS/Dijkstra) |
| CV parsing | PyPDF2 · python-docx |
| Frontend | Vanilla HTML/CSS/JS · SVG graph renderer |
| Deploy | Docker · Render |

---

## Project structure

```
talent-angels/
├── app/
│   └── main.py          # Flask app + all three agents
├── templates/
│   └── index.html       # Single-page UI
├── static/
│   ├── css/style.css
│   └── js/app.js
├── Dockerfile
├── render.yaml
├── requirements.txt
└── README.md
```

---

## Run locally

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_ORG/talent-angels.git
cd talent-angels
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...    # Linux/macOS
set ANTHROPIC_API_KEY=sk-ant-...       # Windows CMD
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

### 3. Run

```bash
python app/main.py
```

Open `http://localhost:5000` in your browser.

---

## Deploy to Render

### Option A — render.yaml (recommended)

1. Fork this repo to your GitHub account.
2. Go to [render.com](https://render.com) → **New** → **Blueprint**.
3. Connect your repo — Render reads `render.yaml` automatically.
4. In the Render dashboard, go to **Environment** → add `ANTHROPIC_API_KEY` with your key.
5. Deploy. Your app will be live at `https://talent-angels.onrender.com` (or similar).

### Option B — Manual Web Service

1. Render → **New Web Service** → connect your repo.
2. Runtime: **Docker**.
3. Environment variable: `ANTHROPIC_API_KEY = sk-ant-...`
4. Deploy.

> **Free tier note:** Render free instances spin down after 15 min of inactivity. The first request after sleep takes ~30 s. Upgrade to Starter ($7/mo) for always-on.

---

## How the knowledge graph works

Skills are nodes in a directed graph **G = (V, E)** where an edge `u → v` means *"u is a prerequisite for v"*. The three agents implement classic graph algorithms:

- **Locator** — semantic search via LLM embeddings
- **Connector** — neighborhood query: `G.predecessors(v)` and `G.successors(v)`
- **Pathfinder** — shortest path: `nx.shortest_path(G, source, target)` (BFS-based)

The skill taxonomy is a sample from ESCO, O\*NET, and SFIA. For production, connect to the official APIs:
- ESCO API (free, public): `https://ec.europa.eu/esco/api`
- O\*NET Web Services (free registration): `https://services.onetcenter.org`
- Lightcast Skills API: `https://lightcast.io/open-skills`

---

## Extending the project

| Goal | Where to change |
|------|----------------|
| Add more skills | `TAXONOMY` dict in `app/main.py` |
| Connect to ESCO API | `ConectorTaxonomias` class (add to main.py) |
| Persist results | Add SQLite / PostgreSQL session storage |
| Add Neo4j | Replace NetworkX graph with py2neo driver |
| Add authentication | Flask-Login + user profiles |
| Multilingual | Pass `language` param to ESCO API |

---

## Contributing

This is an open-source mentorship project under the Linux Foundation. See the [Code of Conduct](https://www.lfdecentralizedtrust.org/code-of-conduct).

1. Fork → branch → PR.
2. Issues and feature requests welcome.

---

## License

Apache 2.0 — see [LICENSE](./LICENSE) file.

---

*Learning Tokens · Hyperledger Lab · Linux Foundation Mentorship Program 2026*

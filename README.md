# Literature Survey App — AR + Skeleton-Based Workplace Safety

Self-hosted literature-survey tool. Upload a paper PDF, Gemini extracts the
structured fields (module, dataset, model, objective, strengths,
weaknesses, research gap, etc.), the record is saved to your own Neo4j
AuraDB, and the table + relationship graph update automatically.

## Architecture

```
frontend/index.html  --(fetch)-->  backend (FastAPI)  --(bolt)-->  Neo4j AuraDB
                                         |
                                         +--(HTTPS)--> Gemini API
```

- The **backend** is the only thing that holds your Neo4j password and
  Gemini API key. Never put credentials in the frontend — anyone who
  opens the page's source could read them.
- The **graph shown in the UI is computed fresh on every request** from
  whatever is currently in Neo4j (same-module edges, plus edges where two
  papers share a taxonomy tag Gemini assigned) — there's no separate edge
  store to keep in sync.
- Comments are stored as `(:Comment)-[:ON]->(:Paper)` nodes in the same
  Neo4j database.

## 1. Prerequisites

- Python 3.10+
- A Neo4j AuraDB instance (you said you already have one) — grab its
  connection URI, username, and password from the Aura console. The URI
  looks like `neo4j+s://xxxxxxxx.databases.neo4j.io`.
- A Gemini API key from https://aistudio.google.com/apikey

## 2. Local setup

```bash
cd lit-survey-app/backend
cp .env.example .env
# edit .env and fill in NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, GEMINI_API_KEY

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — the backend serves the frontend directly,
so there's nothing separate to run.

## 3. Running with Docker instead

```bash
cd lit-survey-app
cp backend/.env.example backend/.env
# edit backend/.env with your real values

docker compose up --build
```

Open **http://localhost:8000**.

## 4. Deploying somewhere public

Any host that runs a Docker container or a Python web app works. A few
straightforward options:

### Render.com (easiest)
1. Push this folder to a GitHub repo.
2. New → Web Service → connect the repo.
3. Environment: Docker. Render will find `backend/Dockerfile` automatically
   if you set the Dockerfile path to `backend/Dockerfile` and the Docker
   build context to the repo root — or just point it at the root
   `docker-compose.yml` if using Render's compose support.
4. Add the same environment variables from `.env.example` in Render's
   dashboard (never commit `.env` itself).
5. Deploy. Render gives you a public HTTPS URL.

### Railway / Fly.io
Same pattern: point the platform at `backend/Dockerfile` with build
context = repo root, set the environment variables in their dashboard,
deploy.

### Your own VPS
```bash
git clone <your-repo>
cd lit-survey-app
cp backend/.env.example backend/.env   # fill in real values
docker compose up -d --build
```
Put a reverse proxy (Caddy or nginx) in front of port 8000 for HTTPS and a
real domain.

**Important:** whichever host you use, set the environment variables
through that platform's secrets/env panel — don't bake real credentials
into the image or commit `.env` to git. `.env` is already listed to be
excluded — see `.gitignore` below.

## 5. Add a `.gitignore`

Before pushing to GitHub, create `.gitignore` at the project root:
```
backend/.env
backend/venv/
__pycache__/
*.pyc
```

## 6. Cost and usage notes

- Every PDF upload makes one Gemini API call — this costs API credits per
  Google's pricing for whatever `GEMINI_MODEL` you set. Check current
  pricing at https://ai.google.dev/pricing.
- Consider adding basic auth or an upload password in front of
  `/api/papers/upload` before sharing the link widely, since anyone with
  the URL can currently trigger a Gemini call and write to your database.
  A minimal way: add a shared-secret header check at the top of the
  `upload_paper` function in `backend/main.py`.
- Neo4j Aura's free tier has a node/relationship cap — fine for a
  literature survey of a few hundred papers, but check your plan's limits
  if you expect to scale far beyond that.

## 7. Extending it

- **Module classification wrong on a paper?** Open its detail row; a
  manual-edit UI isn't wired up in this version, but `PUT
  /api/papers/{id}` already accepts any of the fields in
  `neo4j_client.PAPER_FIELDS` — easiest fix is a quick `curl` or adding an
  edit form to `frontend/index.html`.
- **Want the relationship graph smarter?** `neo4j_client.get_graph_data()`
  currently links papers that share a module or a taxonomy keyword.
  You could extend it to also call Gemini with pairs of abstracts and ask
  it to judge relatedness, or compute embedding similarity instead of
  exact keyword overlap.
- **Multiple people uploading?** Everything is already shared through one
  Neo4j database, so this works for a small team as-is. For real
  multi-user permissions (who can delete vs. only comment), you'd add an
  auth layer — not included here to keep the app simple to self-host.

## File map

```
lit-survey-app/
├── backend/
│   ├── main.py              FastAPI app, all API routes
│   ├── neo4j_client.py      Neo4j read/write + graph computation
│   ├── gemini_extractor.py  PDF text -> structured JSON via Gemini
│   ├── pdf_utils.py         PDF -> plain text
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   └── index.html           Table + graph + upload UI, single file
├── docker-compose.yml
└── README.md
```

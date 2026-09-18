"""
Literature Survey app backend.

Endpoints:
  POST   /api/papers/upload      -- upload a PDF, Gemini extracts fields, saved to Neo4j
  GET    /api/papers             -- list all papers
  GET    /api/papers/{id}        -- one paper
  PUT    /api/papers/{id}        -- manually edit a paper's fields
  DELETE /api/papers/{id}        -- delete a paper
  GET    /api/graph              -- nodes + edges for the relationship graph
  GET    /api/papers/{id}/comments   -- list comments on a paper
  POST   /api/papers/{id}/comments   -- add a comment

Run locally:
  uvicorn main:app --reload --port 8000
"""

import os
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

import neo4j_client as db
import gemini_extractor
import pdf_utils

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lit-survey")

app = FastAPI(title="Literature Survey API")

# In production, replace "*" with your actual frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    try:
        db.verify_connectivity()
        logger.info("Connected to Neo4j.")
    except Exception as e:
        logger.warning(f"Neo4j connectivity check failed at startup: {e}")


@app.on_event("shutdown")
def shutdown():
    db.close_driver()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/papers/upload")
async def upload_paper(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf",) and not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file.")

    file_bytes = await file.read()
    try:
        text = pdf_utils.extract_text(file_bytes)
    except Exception as e:
        raise HTTPException(400, f"Could not read PDF: {e}")

    if not text.strip():
        raise HTTPException(
            400,
            "No extractable text found in this PDF (it may be a scanned "
            "image without OCR). Try a text-based PDF.",
        )

    try:
        fields = gemini_extractor.extract_paper_info(text)
    except gemini_extractor.ExtractionError as e:
        logger.exception("Gemini extraction failed")
        raise HTTPException(502, f"Gemini extraction failed: {e}")
    except Exception as e:
        # Catch anything unexpected from the Gemini SDK too, so it shows
        # up here instead of as a bare 500 with no detail.
        logger.exception("Unexpected error calling Gemini")
        raise HTTPException(502, f"Unexpected error calling Gemini: {e}")

    if not fields.get("link"):
        fields["link"] = ""

    try:
        paper = db.create_paper(fields)
    except Exception as e:
        logger.exception("Could not save to Neo4j")
        raise HTTPException(500, f"Could not save to Neo4j: {e}")

    return paper


@app.get("/api/papers")
def list_papers():
    try:
        return db.get_all_papers()
    except Exception as e:
        raise HTTPException(500, f"Could not read from Neo4j: {e}")


@app.get("/api/papers/{paper_id}")
def get_paper(paper_id: str):
    paper = db.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "Paper not found.")
    return paper


@app.put("/api/papers/{paper_id}")
def edit_paper(paper_id: str, fields: dict = Body(...)):
    paper = db.update_paper(paper_id, fields)
    if not paper:
        raise HTTPException(404, "Paper not found.")
    return paper


@app.delete("/api/papers/{paper_id}")
def remove_paper(paper_id: str):
    db.delete_paper(paper_id)
    return {"deleted": paper_id}


@app.get("/api/graph")
def graph_data():
    try:
        return db.get_graph_data()
    except Exception as e:
        raise HTTPException(500, f"Could not compute graph: {e}")


@app.get("/api/papers/{paper_id}/comments")
def list_comments(paper_id: str):
    return db.get_comments(paper_id)


@app.post("/api/papers/{paper_id}/comments")
def create_comment(paper_id: str, body: dict = Body(...)):
    author = body.get("author", "Anonymous")
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "Comment text cannot be empty.")
    comment = db.add_comment(paper_id, author, text)
    if not comment:
        raise HTTPException(404, "Paper not found.")
    return comment


# --- serve the frontend ---------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
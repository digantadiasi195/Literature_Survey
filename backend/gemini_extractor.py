"""
Calls the Gemini API to turn raw paper text into the structured fields
the literature survey table uses.

Uses Google's official `google-generativeai` SDK. Get an API key from
https://aistudio.google.com/apikey and set GEMINI_API_KEY in your .env.

GEMINI_MODEL is configurable via env var because model names change
over time -- check https://ai.google.dev/gemini-api/docs/models for
the current list and set GEMINI_MODEL accordingly if the default below
is no longer available on your account.
"""

import os
import json
import re
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

MODULE_DEFINITIONS = """
1 = Vision-Based Human Monitoring (real-time camera / sensor input)
2 = Pose Estimation (human skeleton detection)
3 = Skeleton-Based Action Recognition
4 = Multi-Step Task Recognition (procedural / activity recognition)
5 = AR for Industrial Safety (safe/danger zone visualization)
6 = Safety Monitoring & Risk Assessment (risk decision fusion)
7 = AR Visualization & Human-Computer Interaction (warning/alert display)
"""

EXTRACTION_PROMPT = """You are helping a PhD student build a literature-survey
spreadsheet for a thesis on AR-integrated skeleton-based human activity
recognition for workplace safety. Read the paper text below and extract the
following fields as a single JSON object with EXACTLY these keys:

- "module": integer 1-7, the single best-fitting module from this list:
{modules}
- "title": the paper's full title
- "year": publication year as an integer (best estimate if not explicit)
- "venue": journal or conference name
- "dataset": dataset(s) used, or "N/A" if none
- "model": the method/model/architecture used
- "objective": one sentence, what the paper set out to do
- "best_performance": key reported results/metrics, or "N/A"
- "strengths": 1-3 sentences
- "weaknesses": 1-3 sentences
- "research_gap": what the paper's own limitations/future-work section says
  is missing, in your own words
- "relevant": boolean, true if genuinely relevant to AR + skeleton-based
  industrial safety research, false otherwise
- "taxonomy": 3-6 short comma-separated keyword tags for this paper (used to
  compute relationships between papers in the survey graph -- reuse common
  terms like "skeleton action recognition", "AR safety zone", "pose
  estimation", "occlusion", "risk fusion", "digital twin", etc. where they
  apply, so related papers share tags)
- "evaluation_metrics": metrics used (e.g. "F1, accuracy, mAP"), or "N/A"
- "hardware_constraint": any hardware/compute constraints mentioned, or "N/A"

Respond with ONLY the JSON object, no markdown fences, no commentary.

PAPER TEXT:
---
{text}
---
"""


class ExtractionError(Exception):
    pass


def _configure():
    if not GEMINI_API_KEY:
        raise ExtractionError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )
    genai.configure(api_key=GEMINI_API_KEY)


def _parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    # Strip markdown code fences if the model added them anyway.
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # Last resort: grab the first {...} block in the response.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise ExtractionError(f"Gemini did not return valid JSON: {e}\nRaw: {raw[:500]}")


def extract_paper_info(paper_text: str) -> dict:
    """Send paper text to Gemini and return the structured field dict.
    Raises ExtractionError on failure."""
    _configure()
    model = genai.GenerativeModel(GEMINI_MODEL)
    prompt = EXTRACTION_PROMPT.format(modules=MODULE_DEFINITIONS, text=paper_text)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
    except Exception as e:
        raise ExtractionError(f"Gemini API call failed: {e}")

    if not response.text:
        raise ExtractionError("Gemini returned an empty response.")

    data = _parse_json_response(response.text)

    # Fill in any missing keys defensively so the frontend never breaks.
    defaults = {
        "module": 0, "title": "Untitled", "year": 0, "venue": "", "dataset": "",
        "model": "", "objective": "", "best_performance": "", "strengths": "",
        "weaknesses": "", "research_gap": "", "relevant": False, "taxonomy": "",
        "evaluation_metrics": "", "hardware_constraint": "",
    }
    for k, v in defaults.items():
        data.setdefault(k, v)
    return data

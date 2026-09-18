"""
Standalone Gemini connectivity test -- run this directly to see EXACTLY
what's failing, with the full error, before touching the rest of the app.

Usage (from the backend/ directory, same env you run uvicorn in):
    python test_gemini.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY", "")
model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

print(f"GEMINI_API_KEY loaded: {'yes (' + api_key[:6] + '...)' if api_key else 'NO -- .env not loaded or key missing!'}")
print(f"GEMINI_MODEL: {model_name}")
print("-" * 60)

if not api_key:
    print("STOP: GEMINI_API_KEY is empty. Check that:")
    print("  1. backend/.env exists (not just .env.example)")
    print("  2. it contains a real line: GEMINI_API_KEY=AIza...")
    print("  3. you're running this script from the backend/ directory")
    raise SystemExit(1)

import google.generativeai as genai

genai.configure(api_key=api_key)

print("Step 1: listing models available to this API key...")
try:
    available = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    print(f"  {len(available)} models support generateContent. First 10:")
    for m in available[:10]:
        print("   -", m)
    if not any(model_name in m for m in available):
        print(f"\n  ⚠ '{model_name}' is NOT in that list. This is almost certainly your")
        print(f"    502 error. Set GEMINI_MODEL in .env to one of the names above")
        print(f"    (try 'models/gemini-1.5-flash' or whatever generateContent model")
        print(f"    is listed) and try again.")
except Exception as e:
    print(f"  FAILED to list models: {type(e).__name__}: {e}")
    print("  This usually means the API key itself is invalid or has no access.")
    print("  Get a fresh key at https://aistudio.google.com/apikey")
    raise SystemExit(1)

print("-" * 60)
print(f"Step 2: sending a minimal test prompt to '{model_name}'...")
try:
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Reply with exactly: OK")
    print("  SUCCESS. Response:", response.text)
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    print("\n  Common causes:")
    print("  - Model name wrong for this SDK version/region (see Step 1's list)")
    print("  - Billing/quota not enabled on this Google Cloud project")
    print("  - google-generativeai package version mismatch (try: pip install -U google-generativeai)")
    raise SystemExit(1)

print("-" * 60)
print("Step 3: testing structured JSON output (what the real app uses)...")
try:
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        'Return JSON: {"hello": "world"}',
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    print("  SUCCESS. Response:", response.text)
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    print("\n  If Step 2 worked but Step 3 didn't, the issue is specifically")
    print("  with response_mime_type='application/json' -- some models/SDK")
    print("  versions don't support it. Tell Claude this and it'll switch")
    print("  gemini_extractor.py to a version that parses JSON from plain text")
    print("  instead of relying on this parameter.")
    raise SystemExit(1)

print("-" * 60)
print("All three checks passed -- Gemini itself is working correctly.")
print("If /api/papers/upload still fails, the problem is elsewhere")
print("(PDF text extraction or Neo4j write) -- check the uvicorn terminal")
print("for the full traceback now that logging has been improved.")

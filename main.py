from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import create_client
import os, base64, json, uuid
import PIL.Image, io
import datetime

# ── Load env & configure Gemini ──────────────────────────────────────────────
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SUPABASE_URL   = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY", "")

if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY is not set — AI features will fail.")
if not SUPABASE_URL or not SUPABASE_KEY:
    print("[WARNING] Supabase credentials are not set — DB features will fail.")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
MODEL = "gemini-2.5-flash-lite"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(title="VoxCivica API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request models ────────────────────────────────────────────────────────────
class ComplaintRequest(BaseModel):
    complaint: str
    location: str = "Not specified"
    language: str = "English"
    urgency: str = "polite"

class PhotoRequest(BaseModel):
    image_base64: str

class ClusterRequest(BaseModel):
    complaint_ids: list[str]
    location: str = "the reported area"

class SaveRequest(BaseModel):
    user_email: str = "anonymous@example.com"
    location_name: str = "Unknown"
    text: str
    petition: str = ""
    lat: float
    lng: float
    category: str = "general"
    tone: str = "polite"
    language: str = "English"
    urgency_level: int = 1

class ValidateRequest(BaseModel):
    complaint: str

class RatePetitionRequest(BaseModel):
    petition_text: str

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "VoxCivica API is running", "model": MODEL}


@app.post("/generate-petition")
def generate_petition(req: ComplaintRequest):
    try:
        language_instruction = {
            "Tamil": "முழு மனுவையும் தமிழிலேயே எழுதவும். ஆங்கிலம் பயன்படுத்தாதீர்கள்.",
            "Hindi": "पूरी याचिका केवल हिंदी में लिखें। अंग्रेजी का उपयोग न करें।",
            "Telugu": "మొత్తం పిటిషన్ తెలుగులో మాత్రమే రాయండి. ఆంగ్లం వాడవద్దు.",
            "English": "Write the entire petition in formal English."
        }.get(req.language, "Write the entire petition in formal English.")

        tone_guide = {
            "polite": "Use a respectful, patient, and cooperative tone.",
            "firm": "Use a firm, assertive tone that highlights urgency and safety risks.",
            "formal": "Use strict legal-notice language. Reference civic duty and potential escalation."
        }.get(req.urgency, "Use a respectful tone.")

        prompt = f"""You are a senior civic legal document expert in India with 20 years of experience drafting government petitions.

LANGUAGE RULE: {language_instruction}
TONE RULE: {tone_guide}

Your task: Transform the citizen's informal complaint below into a world-class formal government petition.

Citizen's complaint: "{req.complaint}"
Location of issue: "{req.location}"

You MUST follow this exact structure. Do not skip any section:

---
[SUBJECT LINE - one sentence describing the issue]

To,
The [Correct Government Department Name],
[City/Region]

Respected Sir/Madam,

[PARAGRAPH 1 - 3-4 sentences: Introduce yourself as a concerned citizen. State the exact location and nature of the civic problem clearly.]

[PARAGRAPH 2 - 3-4 sentences: Describe the impact on daily life, safety risks, and how long the issue has persisted.]

[PARAGRAPH 3 - 2-3 sentences: Make a specific, time-bound demand. Request acknowledgment within 7 working days.]

Thanking you,
A Concerned Citizen
{req.location}

DEPARTMENT: [Name the single most responsible government department]
---

Write at minimum 200 words. Be specific. Do not be vague."""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return {"petition": response.text, "status": "success"}

    except Exception as e:
        print(f"[ERROR] /generate-petition: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-photo")
def analyze_photo(req: PhotoRequest):
    try:
        img_data = base64.b64decode(req.image_base64)
        img = PIL.Image.open(io.BytesIO(img_data))

        # Convert PIL image → bytes for the SDK
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        img_bytes = buf.getvalue()

        prompt = """Look at this image and describe the civic issue
you see in 2-3 formal sentences, as it would appear
in an official government complaint letter.
Be specific about what is visible and any potential safety risk."""

        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_text(text=prompt),
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            ],
        )
        return {"description": response.text}

    except Exception as e:
        print(f"[ERROR] /analyze-photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate-complaint")
def validate_complaint(req: ValidateRequest):
    try:
        prompt = f"""Analyze this civic complaint and rate its severity from 1 to 5.
1-2: Minor inconvenience.
3: Moderate issue.
4-5: Safety hazard / URGENT.
Complaint: {req.complaint}
Reply ONLY with JSON:
{{"urgency_level": 4}}"""
        response = client.models.generate_content(model=MODEL, contents=prompt)
        raw = response.text.strip()
        if raw.startswith("```json"): raw = raw[7:-3]
        elif raw.startswith("```"): raw = raw[3:-3]
        data = json.loads(raw)
        return {"urgency_level": data.get("urgency_level", 1)}
    except Exception as e:
        print(f"[ERROR] /validate-complaint: {e}")
        return {"urgency_level": 1}

@app.post("/rate-petition")
def rate_petition(req: RatePetitionRequest):
    try:
        prompt = f"""Rate this government petition on a scale of 1-10
for: clarity, formality, specificity, and persuasiveness.

Petition: {req.petition_text}

Reply ONLY with JSON:
{{"score": 8, "strongest_part": "...", "one_improvement": "..."}}"""
        response = client.models.generate_content(model=MODEL, contents=prompt)
        raw = response.text.strip()
        if raw.startswith("```json"): raw = raw[7:-3]
        elif raw.startswith("```"): raw = raw[3:-3]
        data = json.loads(raw)
        return data
    except Exception as e:
        print(f"[ERROR] /rate-petition: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class FlagRequest(BaseModel):
    complaint_id: str
    user_email: str = "anonymous@example.com"
    reason: str = "Fake"

@app.post("/save-complaint")
def save_complaint(req: SaveRequest):
    try:
        # Rate Limiting check: max 5 complaints per 24 hours per user
        # Only apply if it's a real user email (not anonymous)
        if req.user_email and "@" in req.user_email and req.user_email != "anonymous@example.com":
            from datetime import datetime, timedelta
            cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
            
            recent = supabase.table("complaints")\
                .select("id")\
                .eq("user_email", req.user_email)\
                .gte("created_at", cutoff)\
                .execute()
                
            if len(recent.data) >= 5:
                raise HTTPException(
                    status_code=429, 
                    detail=f"Limit reached for {req.user_email}: You can only submit 5 complaints every 24 hours."
                )

        result = supabase.table("complaints").insert({
            "user_email": req.user_email,
            "location_name": req.location_name,
            "complaint_text": req.text,
            "petition_text": req.petition,
            "category": req.category,
            "lat": req.lat,
            "lng": req.lng,
            "tone": req.tone,
            "language": req.language,
            "status": "active",
            "urgency_level": req.urgency_level
        }).execute()
        return {"saved": True, "id": result.data[0]["id"]}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] /save-complaint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/flag-complaint")
def flag_complaint(req: FlagRequest):
    try:
        # Check current flags for this complaint
        # (Assuming we track flag count or rely on frontend. For now, let's just increment a flag_count field or query flags)
        # Since we removed login, we will track flags in a 'flags' table by email
        
        # 1. Insert the flag
        supabase.table("flags").insert({
            "complaint_id": req.complaint_id,
            "flagged_by_email": req.user_email,
            "reason": req.reason
        }).execute()

        # 2. Check total flags
        flags_result = supabase.table("flags")\
            .select("id", count="exact")\
            .eq("complaint_id", req.complaint_id)\
            .execute()
            
        flag_count = flags_result.count if flags_result.count else len(flags_result.data)

        # 3. If >= 3 flags, update status to hide it
        if flag_count >= 3:
            supabase.table("complaints")\
                .update({"status": "under_review"})\
                .eq("id", req.complaint_id)\
                .execute()
                
        return {"flagged": True, "flag_count": flag_count}
    except Exception as e:
        # If they already flagged it, it might throw a unique constraint error, which is fine
        print(f"[ERROR] /flag-complaint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class UpvoteRequest(BaseModel):
    complaint_id: str
    user_email: str

@app.post("/upvote-complaint")
def upvote_complaint(req: UpvoteRequest):
    try:
        supabase.table("upvotes").insert({
            "complaint_id": req.complaint_id,
            "user_email": req.user_email
        }).execute()
        return {"upvoted": True}
    except Exception as e:
        print(f"[ERROR] /upvote-complaint: {e}")
        # Could fail if they already upvoted, which is fine
        return {"upvoted": False, "reason": str(e)}

@app.get("/my-petitions")
def get_my_petitions(user_email: str):
    try:
        result = supabase.table("complaints")\
            .select("*")\
            .eq("user_email", user_email)\
            .order("created_at", desc=True)\
            .execute()
        return {"petitions": result.data}
    except Exception as e:
        print(f"[ERROR] /my-petitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ResolveRequest(BaseModel):
    complaint_id: str
    user_email: str

@app.post("/resolve-complaint")
def resolve_complaint(req: ResolveRequest):
    try:
        supabase.table("complaints")\
            .update({"status": "resolved"})\
            .eq("id", req.complaint_id)\
            .eq("user_email", req.user_email)\
            .execute()
        return {"resolved": True}
    except Exception as e:
        print(f"[ERROR] /resolve-complaint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-complaints")
def get_complaints():
    try:
        # Only fetch complaints that are not hidden (under_review)
        result = supabase.table("complaints")\
            .select("*")\
            .neq("status", "under_review")\
            .order("created_at", desc=True)\
            .limit(100)\
            .execute()
        
        # We need to map the supabase schema back to what the frontend expects 
        # (lat, lng, text, category, petition).
        mapped_complaints = []
        for c in result.data:
            mapped_complaints.append({
                "id": c.get("id"),
                "text": c.get("complaint_text"),
                "petition": c.get("petition_text"),
                "category": c.get("category", "general"),
                "lat": c.get("lat"),
                "lng": c.get("lng"),
                "upvote_count": c.get("upvote_count", 0),
                "urgency_level": c.get("urgency_level", 1)
            })
        
        return {"complaints": mapped_complaints}
    except Exception as e:
        print(f"[ERROR] /get-complaints: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cluster-petition")
def cluster_petition(req: ClusterRequest):
    try:
        # Get from supabase instead of db.json
        result = supabase.table("complaints")\
            .select("*")\
            .in_("id", req.complaint_ids)\
            .execute()
            
        matched = result.data

        if not matched:
            return {"error": "No complaints found for given IDs"}

        texts = "\n".join(
            [f"{i+1}. {c.get('complaint_text', '')}" for i, c in enumerate(matched)]
        )
        prompt = f"""These {len(matched)} citizens near {req.location}
reported civic issues:
{texts}

Write ONE powerful collective petition that:
1. Opens by stating {len(matched)} households are affected
2. Clearly describes all the issues
3. Is addressed to the correct authority
4. Demands urgent action within 7 days
5. Has a strong, professional closing"""

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return {
            "collective_petition": response.text,
            "count": len(matched),
        }

    except Exception as e:
        print(f"[ERROR] /cluster-petition: {e}")
        raise HTTPException(status_code=500, detail=str(e))
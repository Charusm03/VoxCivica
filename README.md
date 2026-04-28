# VoxCivica AI — Backend API

FastAPI backend serving as the AI orchestration engine for VoxCivica AI.
Handles all Gemini API calls, complaint processing, and Supabase database operations.

🌐 **Frontend:** [voxcivica-ai.web.app](https://voxcivica-ai.web.app)
📦 **Full Project:** [https://github.com/Charusm03/VoxCivicaa](https://github.com/Charusm03/VoxCivicaa)

---

## What This Service Does

This backend receives requests from the Flutter frontend and:

- Calls **Google Gemini 1.5 Flash** to generate formal petitions from informal complaints
- Calls **Gemini Vision** to analyze uploaded civic issue photos
- Validates complaints, scores severity, and detects duplicates using AI
- Reads and writes all complaint, profile, upvote, and flag data to **Supabase**
- Enforces rate limiting (5 complaints per user per 24 hours)
- Runs the collective petition clustering engine

---

## Tech Stack

| | |
|---|---|
| Framework | FastAPI (Python 3.11) |
| AI | Google Gemini 1.5 Flash |
| Database | Supabase (PostgreSQL) |
| Hosting | Railway |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check — confirms API is running |
| POST | `/generate-petition` | Generates a formal petition from a raw complaint |
| POST | `/analyze-photo` | Gemini Vision analyzes a civic issue photo |
| POST | `/validate-complaint` | AI validates if the complaint is a genuine civic issue |
| POST | `/save-complaint` | Saves a complaint + petition to Supabase |
| GET | `/get-complaints` | Returns all complaints for the community map |
| POST | `/cluster-petition` | Merges nearby complaints into one collective petition |
| POST | `/check-duplicate` | Checks if the same issue was already reported nearby |

---

## Environment Variables

Set these in your Railway project → Variables tab:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_KEY=your_supabase_anon_key_here
```

## Local Development

```bash
# Clone and enter the backend folder
git clone https://github.com/yourusername/voxcivica-backend.git
cd voxcivica-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your keys
cp .env.example .env

# Run locally
uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` to see and test all endpoints interactively.

---

## Deployment on Railway

This repo is configured to deploy automatically on Railway.

1. Connect this repo to a new Railway project
2. Add the three environment variables listed above
3. Railway auto-detects the `requirements.txt` and starts the service
4. Set the start command if needed:
uvicorn main:app --host 0.0.0.0 --port $PORT

Railway injects `$PORT` automatically — do not hardcode a port number.

---

## Project Structure
voxcivica-backend/
├── main.py            # All FastAPI routes and Gemini logic
├── requirements.txt   # Python dependencies
├── Dockerfile         # Optional — Railway works without it
├── .env.example       # Environment variable template
├── .gitignore         # Excludes .env and pycache
└── README.md

---

## Dependencies
fastapi
uvicorn
google-generativeai
python-dotenv
supabase
pillow

---

## CORS

CORS is configured to allow all origins (`*`) so the Flutter web frontend
at `voxcivica-ai.web.app` can reach this API without restrictions.
Restrict this to your frontend domain in production.

---

## Related

- **Frontend repo:** Flutter Web app hosted on Firebase Hosting
- **Database:** Supabase project with complaints, profiles, upvotes, flags tables
- **Full project README:** includes architecture diagram, SDG mapping, and setup guide

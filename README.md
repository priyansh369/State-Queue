## Smart Hospital Management System

Full-stack hospital management SaaS demo with:

- **Backend**: FastAPI + SQLite (`backend/`)
- **Frontend**: React + Vite (`frontend/`)
- **Panels**: Patient, Doctor, Reception (role-based)

### Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:5173`

### Notes

- Use **Register** to create patient/doctor/receptionist accounts.
- Login redirects to the correct panel based on role.
- Emergency patients are surfaced at the top of queues, with basic wait-time estimation.

### Optional: Twilio SMS Notifications

To enable SMS on `NEW_APPOINTMENT`, `STATUS_UPDATED`, and "now serving soon" reminders, set:

```bash
SMS_ENABLED=true
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
SMS_SOON_THRESHOLD_MINUTES=10
SMS_SOON_COOLDOWN_MINUTES=15
```

If these are not set, SMS functions are safely skipped.

### Deployment (Vercel + Render)

1. Deploy backend on Render

- Push this repo to GitHub.
- In Render, create a new Blueprint service and select this repo.
- Render will read `render.yaml` and create the FastAPI service.
- Set `CORS_ORIGINS` in Render to your frontend URL (for example `https://your-app.vercel.app`).

2. Deploy frontend on Vercel

- Import the same repo in Vercel.
- Set project root to `frontend`.
- Add environment variables:
  - `VITE_API_BASE_URL=https://<your-render-backend>.onrender.com`
  - `VITE_WS_URL=wss://<your-render-backend>.onrender.com/ws`
- Deploy.

3. Update backend CORS after frontend is live

- Set backend `CORS_ORIGINS` to include:
  - your Vercel URL
  - local dev URL (`http://localhost:5173`) if needed


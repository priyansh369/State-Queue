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
uvicorn backend.main:app --reload --port 8000
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


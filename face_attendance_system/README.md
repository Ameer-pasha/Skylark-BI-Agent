# 🎓 Smart Attendance System

A complete **face-recognition attendance system** for students. Register a
student's face once, then let a live camera recognise them and mark
attendance automatically — with a modern, animated web UI.

| Layer | Tech |
|---|---|
| Backend | Python 3.10/3.11 · Flask · Flask-SQLAlchemy · Flask-CORS |
| Face engine | InsightFace (`buffalo_l` → RetinaFace + ArcFace 512-d) · ONNX Runtime |
| Database | SQLite (`database/attendance.db`) |
| Frontend | HTML/CSS/JS · Tailwind CSS · vanilla JS (`fetch` + `getUserMedia`) |

---

## 📁 Project structure

```
face_attendance_system/
├── app.py                     # Flask entry point (runs the server)
├── config.py                  # Configuration (.env overrides)
├── requirements.txt           # Python dependencies
├── .env.example               # Copy to .env
├── models/
│   └── face_engine.py         # InsightFace wrapper (FaceEngine class)
├── database/
│   ├── models.py              # SQLAlchemy models (Student, Attendance)
│   └── attendance.db          # created automatically at first run
├── routes/
│   ├── student_routes.py      # /api/register, /api/students …
│   └── attendance_routes.py   # /api/recognize, /api/mark-attendance …
├── static/
│   ├── css/style.css          # design system + animations
│   ├── js/app.js              # shared helpers (toasts, theme, fetch)
│   └── uploads/               # student photos
├── templates/
│   ├── base.html              # layout, sidebar, dark mode
│   ├── dashboard.html         # stats + recent activity
│   ├── register.html          # webcam capture / upload
│   ├── live_attendance.html   # live recognition + auto-mark
│   ├── records.html           # records table + Excel export
│   └── students.html          # student management (edit/delete)
├── scripts/
│   ├── install_insightface.sh # installs insightface (see note below)
│   ├── test_face_engine.py    # standalone face-engine verification
│   ├── test_database.py       # DB models + constraints verification
│   └── seed_demo.py           # optional demo data
└── utils/
    ├── helpers.py             # image/date/status helpers
    └── registry.py            # in-memory embedding cache
```

---

## ⚙️ Setup (Step by step)

> Requires **Python 3.10 or 3.11**. Everything installs inside a virtual
> environment — nothing is installed system-wide.

### 1. Create & activate the virtual environment

```bash
cd face_attendance_system

# create
python -m venv venv

# activate — Windows
venv\Scripts\activate

# activate — macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Then install **InsightFace** (the 0.7.3 release ships source-only and tries
to compile a C++ 3D-mesh extension that is *not* used by face
detection/recognition, and which needs CPython dev headers). The helper
script patches that extension out and installs a pure-Python build:

```bash
bash scripts/install_insightface.sh
```

> On a normal machine with `python3-dev` / `build-essential` installed, a
> plain `pip install insightface==0.7.3` also works.

### 3. Configure (optional)

```bash
cp .env.example .env   # then edit values if needed
```

Key settings:

| Variable | Default | Meaning |
|---|---|---|
| `FACE_MATCH_THRESHOLD` | `0.45` | cosine-similarity threshold (0.45–0.5) |
| `DETECTION_THRESHOLD` | `0.5` | RetinaFace detection confidence |
| `LATE_AFTER` | `09:15` | students marked after this time get status `Late` |
| `PORT` | `5000` | server port |

### 4. Run the server

```bash
python app.py
```

Open **http://localhost:5000**. The `buffalo_l` model pack downloads
automatically on first run (one-time, ~330 MB).

---

## 🧪 Verifying each layer before the UI

```bash
# DB models + unique-constraint test (in-memory, no side effects)
python scripts/test_database.py

# Face engine test — loads buffalo_l, generates two synthetic faces,
# prints embeddings + cosine similarity results
python scripts/test_face_engine.py
```

### Test the API with curl

```bash
# register (JSON base64 image)
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Aisha","roll_no":"CS-011","class_section":"10-A","image":"<data-url>"}'

# list students
curl http://localhost:5000/api/students

# recognize a frame
curl -X POST http://localhost:5000/api/recognize \
  -H "Content-Type: application/json" \
  -d '{"image":"<data-url>"}'

# mark attendance
curl -X POST http://localhost:5000/api/mark-attendance \
  -H "Content-Type: application/json" \
  -d '{"student_id":1}'

# attendance by date
curl "http://localhost:5000/api/attendance?date=2026-09-10"

# today's summary
curl http://localhost:5000/api/attendance/summary

# Excel export
curl -OJ "http://localhost:5000/api/attendance/export?date=2026-09-10"
```

---

## 🔌 API reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/register` | Register a student (multipart `image` file **or** JSON base64 `image`) |
| `GET` | `/api/students` | List all students |
| `GET` | `/api/students/<id>` | Get one student |
| `PUT` | `/api/students/<id>` | Edit name / roll / class (optionally new photo) |
| `DELETE` | `/api/students/<id>` | Delete a student (+ their attendance) |
| `POST` | `/api/recognize` | Detect & recognise faces in a base64 frame (multi-face) |
| `POST` | `/api/mark-attendance` | Mark attendance for a `student_id` (duplicate-checked) |
| `GET` | `/api/attendance` | Records with `date`, `class_section`, `search`, pagination |
| `GET` | `/api/attendance/summary` | Today's counts + recent activity |
| `GET` | `/api/attendance/export` | Download `.xlsx` (honours the same filters) |
| `GET` | `/api/health` | Server + face-engine status |

Error responses use a consistent shape: `{ "error": "human-readable message" }`
with the right status code (400 invalid input, 409 duplicate roll number,
422 no/multiple/low-quality face, 404 not found, 500 server error).

---

## 🧠 How recognition works

1. **Registration** → the uploaded photo is run through `FaceEngine` which
   detects the face and returns a 512-d ArcFace embedding, stored as a BLOB
   on the `students` row (and cached in memory for fast matching).
2. **Live attendance** → every ~1.2 s a frame is sent to `/api/recognize`.
   Every face in the frame is detected and embedded; each embedding is
   cosine-compared against all registered students. Similarity ≥ threshold
   (0.45) = match.
3. **Auto-mark** → a match triggers `/api/mark-attendance`, which is
   idempotent per student per day (unique constraint + friendly
   "already marked" message). Time-based status: after `LATE_AFTER` → `Late`.

GPU is used automatically when `onnxruntime-gpu` is installed; otherwise the
engine falls back to CPU.

### Locked-down / offline environments

The full `buffalo_l` pack (`w600k_r50.onnx`, ~165 MB) ships as a GitHub
release asset, which some sandboxes cannot download. In that case:

```bash
bash scripts/fetch_models_fallback.sh
```

This fetches the *compact-but-real* weights — a real SCRFD detector
(`det_500m.onnx`) + a real ArcFace recogniser (`w600k_mbf.onnx`) — from a
public repo and places them where `FaceAnalysis(name="buffalo_l")` looks, so
recognition works identically (slightly lighter model). On a normal machine
this is unnecessary — the full pack auto-downloads on first run.

---

## 🐛 Troubleshooting

- **`ModuleNotFoundError: insightface`** → run `bash scripts/install_insightface.sh`.
- **First request is slow** → the `buffalo_l` model downloads/loads once on
  startup; check `/api/health` for `face_engine_ready`.
- **No face detected** → better lighting, face the camera directly, one face
  per frame. Low-quality frames return a clear 422 message.
- **Wrong/other student matched** → raise `FACE_MATCH_THRESHOLD` in `.env`
  (e.g. 0.5) for stricter matching.
- **`numpy` 2.x warnings** → this project pins `numpy==1.26.4` (InsightFace
  0.7.3 uses `np.int`, removed in numpy 2.0).

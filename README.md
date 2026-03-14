# Контексто — Қазақша 🇰🇿

A full-stack clone of [Contexto.me](https://contexto.me) in Kazakh, built with FastAPI + React.

Players guess a hidden Kazakh word. Each guess returns a **semantic rank** — how close the guess is to the secret word based on real word embeddings trained on Kazakh Wikipedia. Rank #1 means you found the word!

---

## Tech Stack

| Layer | Tech |
|---|---|
| Word Vectors | Meta AI FastText (`wiki.kk.vec`, 300-dim, ~300k Kazakh words) |
| Similarity | Cosine similarity via NumPy (L2-normalized dot product) |
| Backend | Python 3.11 · FastAPI · Uvicorn |
| Frontend | React 18 · Vite · plain CSS |
| Deploy | Docker + Docker Compose · Nginx |

---

## Project Structure

```
kazakhsho/
├── backend/
│   ├── main.py          # FastAPI routes
│   ├── embeddings.py    # Vector loading + cosine similarity engine
│   ├── words.py         # 350+ curated daily words
│   ├── test_api.py      # Pytest test suite
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.jsx     # Entry point
│   │   ├── App.jsx      # Shell + header + rules
│   │   ├── Game.jsx     # Full game logic + UI
│   │   ├── api.js       # API client
│   │   └── index.css    # Design system
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   ├── nginx.conf
│   └── .env.example
├── scripts/
│   ├── download_vectors.sh   # Download FastText Kazakh vectors
│   └── curate_words.py       # Word list inspector + expander
├── data/                     # (created by you) — store vectors here
│   └── wiki.kk.vec           # 600MB — download with script
└── docker-compose.yml
```

---

## Quick Start (Local Development)

### 1. Download Kazakh word vectors

```bash
chmod +x scripts/download_vectors.sh
./scripts/download_vectors.sh
```

This downloads `wiki.kk.vec` (~600 MB) into `./data/`. Run once.

---

### 2. Start the backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy env file
cp .env.example .env

# Start the server
uvicorn main:app --reload --port 8000
```

On first launch, the backend parses the `.vec` file and saves a fast NumPy cache at `./data/kk_vectors.npz`. This takes ~2 minutes once, then loads in seconds on every subsequent start.

Visit `http://localhost:8000` — you should see:
```json
{ "status": "ok", "vocab_loaded": true, "vocab_size": 299458 }
```

---

### 3. Start the frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # set VITE_API_URL=http://localhost:8000
npm run dev
```

Open `http://localhost:3000` — the game is running!

---

## Docker Deployment (Production)

```bash
# 1. Make sure vectors are downloaded
./scripts/download_vectors.sh

# 2. Build and start everything
docker compose up --build -d

# Frontend: http://localhost:80
# Backend:  http://localhost:8000
```

The `./data` folder is mounted into the backend container so vectors persist across rebuilds.

### Deploy to a VPS (e.g. DigitalOcean, Hetzner)

```bash
# On your server:
git clone <your-repo> kazakhsho
cd kazakhsho
./scripts/download_vectors.sh
docker compose up --build -d
```

For HTTPS, put Nginx or Caddy in front with a free Let's Encrypt cert.

---

## API Reference

### `GET /api/daily`
Returns today's game metadata. Does **not** reveal the secret word.

```json
{ "game_id": 183, "total_words": 350, "date": "2024-07-02" }
```

### `POST /api/guess`
Submit a guess for a game.

**Request:**
```json
{ "game_id": 183, "guess": "есік" }
```

**Response:**
```json
{
  "rank": 47,
  "color": "hot",
  "closeness_pct": 72.3,
  "found": false,
  "guess": "есік"
}
```

| color | rank range | meaning |
|---|---|---|
| `winner` | 1 | Exact match — you win! |
| `hot` | 2–99 | Very semantically close |
| `warm` | 100–999 | Somewhat related |
| `cold` | 1000+ | Far away |

### `GET /api/hint/{game_id}?hint_type=category`
Returns a hint. `hint_type`: `category` | `letter` | `close`

```json
{ "game_id": 183, "hint_type": "letter", "hint": "Сөздің бірінші әрпі: «Е»" }
```

---

## Customizing the Word List

Edit `backend/words.py` — add or remove words from the `DAILY_WORDS` list.

Then verify they're in the vocabulary:
```bash
cd kazakhsho
python scripts/curate_words.py check
```

Explore semantic neighbors for any word:
```bash
python scripts/curate_words.py neighbors үй
```

Search for all vocab words with a given prefix:
```bash
python scripts/curate_words.py search қар
```

---

## Running Tests

```bash
cd backend
pip install pytest httpx
pytest test_api.py -v
```

---

## How the Similarity Works

1. At startup, `embeddings.py` loads `wiki.kk.vec` — a 300-dimensional float vector for each of ~300k Kazakh words trained by Meta AI on Kazakh Wikipedia using FastText.

2. All vectors are **L2-normalized** so dot product = cosine similarity (faster, no division needed).

3. When a guess arrives, the backend computes the dot product of the guess vector against all ~300k word vectors in one NumPy matrix multiply (`vectors @ secret_vec`).

4. Words are sorted by similarity — the **rank** is the position of the guess in this sorted list. Rank 1 = the secret word itself.

5. Ranks are cached per secret word so repeated guesses for the same game are instant.

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Default | Description |
|---|---|---|
| `VECTORS_PATH` | `./data/wiki.kk.vec` | Path to FastText vectors |
| `CACHE_PATH` | `./data/kk_vectors.npz` | Path to numpy cache |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS origins (comma-separated) |
| `PORT` | `8000` | Uvicorn port |

### Frontend (`frontend/.env.local`)
| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |

---

## Memory & Performance

| Resource | Approximate value |
|---|---|
| Vector file size | ~600 MB |
| RAM usage (backend) | ~1.2 GB after loading |
| Cold start (parse .vec) | ~2 minutes (once) |
| Warm start (load .npz cache) | ~8 seconds |
| Rank query (p50) | < 50 ms |
| Rank query (cached) | < 1 ms |

For low-RAM servers (< 2 GB), reduce the vocabulary by filtering the .vec file to the top 50k most frequent words using the `scripts/curate_words.py` tooling.

---

## License

MIT — build, fork, deploy, enjoy! 🏇

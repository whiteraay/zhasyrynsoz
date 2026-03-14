from dotenv import load_dotenv
load_dotenv()

import os
import math
import logging
import random
import uuid
from datetime import date, timezone, datetime
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from embeddings import engine
from words import get_daily_word, DAILY_WORDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

custom_games: dict[str, str] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Loading Kazakh word vectors…")
    await engine.load()
    logger.info("Embedding engine ready. Vocab size: %d", len(engine.words))
    yield
    logger.info("Shutting down.")

app = FastAPI(title="Жасырын Сөз API", version="2.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

EPOCH = date(2024, 1, 1)

def get_game_id_for_today() -> int:
    today = datetime.now(timezone.utc).date()
    return (today - EPOCH).days

def game_id_to_word(game_id: int) -> str:
    return get_daily_word(game_id)

def rank_to_color(rank: int) -> str:
    if rank == 1:   return "winner"
    if rank < 100:  return "hot"
    if rank < 1000: return "warm"
    return "cold"

def rank_to_closeness_pct(rank: int, vocab_size: int) -> float:
    if rank == 1: return 100.0
    log_rank = math.log10(max(rank, 1))
    log_max  = math.log10(max(vocab_size, 2))
    return round(max(0.0, (1 - log_rank / log_max) * 100), 1)


class GuessRequest(BaseModel):
    game_id: Optional[int] = None
    custom_token: Optional[str] = None
    guess: str

    @field_validator("guess")
    @classmethod
    def clean_guess(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:       raise ValueError("Guess cannot be empty")
        if len(cleaned) > 60: raise ValueError("Guess too long")
        return cleaned

class GuessResponse(BaseModel):
    rank: int
    color: str
    closeness_pct: float
    found: bool
    guess: str

class DailyResponse(BaseModel):
    game_id: int
    total_words: int
    date: str

class HintResponse(BaseModel):
    game_id: Optional[int]
    hint_type: str
    hint: str

class CustomGameRequest(BaseModel):
    word: str

    @field_validator("word")
    @classmethod
    def clean(cls, v: str) -> str:
        w = v.strip().lower()
        if not w:       raise ValueError("Empty word")
        if len(w) > 40: raise ValueError("Too long")
        return w

class CustomGameResponse(BaseModel):
    custom_token: str


@app.get("/")
async def root():
    return {"status": "ok", "vocab_loaded": engine.is_loaded(), "vocab_size": len(engine.words)}


@app.get("/api/daily", response_model=DailyResponse)
async def get_daily():
    game_id   = get_game_id_for_today()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return DailyResponse(game_id=game_id, total_words=len(DAILY_WORDS), date=today_str)


@app.get("/api/random")
async def get_random_game():
    game_id = random.randint(0, len(DAILY_WORDS) - 1)
    return {"game_id": game_id, "total_words": len(DAILY_WORDS)}


@app.post("/api/custom", response_model=CustomGameResponse)
async def create_custom_game(body: CustomGameRequest):
    if not engine.is_loaded():
        raise HTTPException(503, detail="Engine not ready.")
    if not engine.word_exists(body.word):
        raise HTTPException(422, detail={"code": "WORD_NOT_FOUND", "message": f"«{body.word}» сөздікте жоқ."})
    token = str(uuid.uuid4())[:8]
    custom_games[token] = body.word
    return CustomGameResponse(custom_token=token)


@app.post("/api/guess", response_model=GuessResponse)
async def submit_guess(body: GuessRequest):
    if not engine.is_loaded():
        raise HTTPException(503, detail="Word vectors not yet loaded.")

    if body.custom_token:
        secret = custom_games.get(body.custom_token)
        if not secret:
            raise HTTPException(404, detail="Custom game not found.")
    elif body.game_id is not None:
        secret = game_id_to_word(body.game_id)
    else:
        raise HTTPException(422, detail="Provide game_id or custom_token.")

    guess = body.guess

    if guess == secret:
        return GuessResponse(rank=1, color="winner", closeness_pct=100.0, found=True, guess=guess)

    if not engine.word_exists(secret):
        raise HTTPException(500, detail="Secret word not in vocabulary.")

    if not engine.word_exists(guess):
        raise HTTPException(422, detail={"code": "WORD_NOT_FOUND", "message": f"Сөз табылмады: «{guess}»."})

    rank = engine.get_rank(secret, guess)
    if rank is None:
        raise HTTPException(500, detail="Could not compute rank.")

    return GuessResponse(
        rank=rank,
        color=rank_to_color(rank),
        closeness_pct=rank_to_closeness_pct(rank, len(engine.words)),
        found=False,
        guess=guess,
    )


def _resolve_secret(game_id, custom_token):
    if custom_token:
        secret = custom_games.get(custom_token)
        if not secret:
            raise HTTPException(404, detail="Custom game not found.")
        return secret
    return game_id_to_word(game_id)


def _neighbor_word(neighbors, start, end):
    pool = [w for w, _ in neighbors[start:end]]
    return pool[0] if pool else "?"


@app.get("/api/hint/{game_id}", response_model=HintResponse)
async def get_hint(game_id: int, hint_type: str = "category", offset: int = 0):
    if not engine.is_loaded():
        raise HTTPException(503, detail="Engine not ready.")
    secret = game_id_to_word(game_id)
    hint   = _build_hint(secret, hint_type, offset)
    return HintResponse(game_id=game_id, hint_type=hint_type, hint=hint)


@app.get("/api/hint/custom/{custom_token}", response_model=HintResponse)
async def get_custom_hint(custom_token: str, hint_type: str = "category", offset: int = 0):
    if not engine.is_loaded():
        raise HTTPException(503, detail="Engine not ready.")
    secret = custom_games.get(custom_token)
    if not secret:
        raise HTTPException(404, detail="Custom game not found.")
    hint = _build_hint(secret, hint_type, offset)
    return HintResponse(game_id=None, hint_type=hint_type, hint=hint)


def _build_hint(secret: str, hint_type: str, offset: int = 0) -> str:
    if hint_type == "letter":
        return f"Сөздің бірінші әрпі: «{secret[0].upper()}»"

    if hint_type == "length":
        return f"Сөздің ұзындығы: {len(secret)} әріп"

    if hint_type == "category":
        return _get_category_hint(secret)

    if not engine.word_exists(secret):
        raise HTTPException(500, detail="Secret word not in vocabulary.")

    # Load enough neighbors to cover all offsets
    neighbors = engine.get_top_similar(secret, topn=700)

    if hint_type == "far_word":
        word = _neighbor_word(neighbors, 199, 300)
        return f"Алыс маңайдағы сөз (~200–300 орын): «{word}»"

    if hint_type == "mid_word":
        word = _neighbor_word(neighbors, 49, 80)
        return f"Жақынырақ сөз (~50–80 орын): «{word}»"

    if hint_type == "close_word":
        # Each offset shifts the window by 10 — gives a fresh word each time
        start = 19 + (offset * 10)
        end   = start + 10
        word  = _neighbor_word(neighbors, start, end)
        return f"Жақын сөз (~{start}–{end} орын): «{word}»"

    return _get_category_hint(secret)


_CATEGORIES: list[tuple[set, str]] = [
    ({"су","жер","күн","ай","жұлдыз","тау","дала","орман","теңіз","өзен","көл",
      "қар","жел","бұлт","жаңбыр","найзағай","нұр","жарық","от","жалын","мұз",
      "боран","дауыл","шық","тұман","самал","леп","аяз","қырау","кемпірқосақ",
      "жайлау","алқап","бұлақ","шатқал","жота","шың","тоған","жазира"},
     "Бұл сөз табиғатқа немесе географияға қатысты."),
    ({"шөп","гүл","терек","бұтақ","тамыр","жапырақ","жеміс","дән","тікен","мүк",
      "қайың","емен","шырша","арша","қарағай","тал","жусан","бетеге","сексеуіл",
      "алма","алмұрт","өрік","шабдалы","жүзім","қарбыз","қауын","жидек","бидай",
      "тары","арпа","күріш","жүгері","картоп","пияз","сәбіз"},
     "Бұл өсімдік, жеміс немесе дақылға қатысты сөз."),
    ({"ат","жылқы","түйе","қой","сиыр","ешкі","ит","мысық","қоян","тышқан",
      "түлкі","қасқыр","аю","бұлан","марал","арыстан","барыс","жолбарыс",
      "бүркіт","қыран","лашын","қаз","үйрек","аққу","тырна","тауық","торғай",
      "қарлығаш","кептер","жылан","бақа","тасбақа","балық"},
     "Бұл жануар, хайуан немесе құс."),
    ({"бас","жүз","маңдай","көз","мұрын","ауыз","тіс","тіл","құлақ","мойын",
      "иық","кеуде","арқа","бел","іш","қол","саусақ","аяқ","тізе","табан",
      "шаш","сақал","тырнақ","жүрек","өкпе","бауыр","қан","сүйек","тері","дене"},
     "Бұл адам денесінің мүшесі немесе дене бөлігі."),
    ({"үй","шаңырақ","есік","терезе","төбе","еден","қабырға","бөлме","асхана",
      "үстел","орындық","төсек","жастық","жабу","кілем","шам","айна","сағат",
      "кілт","қазан","шелек","табақ","кесе","шыны","пышақ"},
     "Бұл үй немесе үй мүлкіне қатысты."),
    ({"нан","ет","сорпа","бешбармақ","қазы","сүт","айран","қымыз","шай",
      "май","тұз","қант","ұн","жұмыртқа","ірімшік","бал","қаймақ","тамақ"},
     "Бұл тамақ немесе ішімдікке қатысты."),
    ({"ана","әке","бала","қыз","ұл","апа","аға","іні","ата","әже","немере",
      "туыс","жар","күйеу","келін","дос","көрші","адам","халық","отбасы"},
     "Бұл адам немесе туыстық қарым-қатынасқа қатысты."),
    ({"арман","рух","сезім","ой","ақыл","үміт","қайғы","қуаныш","ашу",
      "қорқыныш","сенім","махаббат","өкініш","намыс","ар","бақыт","шындық",
      "өтірік","жақсылық","тағдыр","ерік","жан"},
     "Бұл сезім, ой немесе рухани ұғым."),
    ({"уақыт","жыл","ай","апта","таң","түн","кеш","жаз","күз","қыс","көктем",
      "бүгін","ертең","кеше","болашақ","өткен","сағат","минут"},
     "Бұл уақытқа немесе мезгілге қатысты."),
    ({"жұмыс","еңбек","кәсіп","дәрігер","ұстаз","жазушы","ақын","суретші",
      "сатушы","егінші","малшы","балықшы","аңшы","ұста","мектеп","білім","ғылым"},
     "Бұл кәсіп, жұмыс немесе білімге қатысты."),
    ({"мемлекет","халық","ұлт","отан","тарих","заң","бостандық","бірлік",
      "соғыс","жеңіс","саясат","үкімет","президент","той","мереке","дін"},
     "Бұл қоғам немесе мәдениетке қатысты."),
    ({"темір","алтын","күміс","мыс","тас","топырақ","құм","саз","ағаш","май"},
     "Бұл материал немесе зат."),
    ({"жол","машина","пойыз","ұшақ","кеме","велосипед","автобус","метро","такси"},
     "Бұл көлік немесе жолсапарға қатысты."),
]

def _get_category_hint(word: str) -> str:
    for word_set, hint in _CATEGORIES:
        if word in word_set:
            return hint
    return "Бұл күнделікті өмірде жиі кездесетін сөз."


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

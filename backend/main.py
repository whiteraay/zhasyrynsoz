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
    if rank == 1: return "winner"
    if rank < 100: return "hot"
    if rank < 1000: return "warm"
    return "cold"

def rank_to_closeness_pct(rank: int, vocab_size: int) -> float:
    if rank == 1: return 100.0
    log_rank = math.log10(max(rank, 1))
    log_max = math.log10(max(vocab_size, 2))
    return round(max(0.0, (1 - log_rank / log_max) * 100), 1)


class GuessRequest(BaseModel):
    game_id: Optional[int] = None
    custom_token: Optional[str] = None
    guess: str

    @field_validator("guess")
    @classmethod
    def clean_guess(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned: raise ValueError("Guess cannot be empty")
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
        if not w: raise ValueError("Empty word")
        if len(w) > 40: raise ValueError("Too long")
        return w

class CustomGameResponse(BaseModel):
    custom_token: str


@app.get("/")
async def root():
    return {"status": "ok", "vocab_loaded": engine.is_loaded(), "vocab_size": len(engine.words)}


@app.get("/api/daily", response_model=DailyResponse)
async def get_daily():
    game_id = get_game_id_for_today()
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

    # Тек DAILY_WORDS ішіндегі сөздер арасындағы rank
    _daily_set = set(w.lower() for w in DAILY_WORDS)
    if guess.lower() not in _daily_set and guess.lower() != secret.lower():
        raise HTTPException(status_code=404, detail="Сөз тізімде жоқ")
    rank = engine.get_rank(secret, guess)
    if rank is None:
        raise HTTPException(500, detail="Could not compute rank.")

    return GuessResponse(
        rank=rank,
        color=rank_to_color(rank),
        closeness_pct=rank_to_closeness_pct(rank, len(DAILY_WORDS)),
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
    hint = _build_hint(secret, hint_type, offset)
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

    from words import DAILY_WORDS as _dw
    _daily_set = set(w.lower() for w in _dw)
    _all = engine.get_top_similar(secret, topn=len(engine.words))
    neighbors = [(w, s) for w, s in _all if w.lower() in _daily_set][:700]

    if hint_type == "far_word":
        word = _neighbor_word(neighbors, 199, 300)
        return f"Алыс маңайдағы сөз (~200–300 орын): «{word}»"

    if hint_type == "mid_word":
        word = _neighbor_word(neighbors, 49, 80)
        return f"Жақынырақ сөз (~50–80 орын): «{word}»"

    if hint_type == "close_word":
        start = 19 + (offset * 10)
        end = start + 10
        word = _neighbor_word(neighbors, start, end)
        return f"Жақын сөз (~{start}–{end} орын): «{word}»"

    return _get_category_hint(secret)


_CATEGORIES: list[tuple[set, str]] = [
    # ── Табиғат & География ──────────────────────────────────────
    ({"су","жер","күн","ай","жұлдыз","тау","дала","орман","теңіз","өзен","көл",
      "қар","жел","бұлт","жаңбыр","найзағай","нұр","жарық","от","жалын","мұз",
      "боран","дауыл","шық","тұман","самал","леп","аяз","қырау","кемпірқосақ",
      "жайлау","алқап","бұлақ","шатқал","жота","шың","тоған","жазира","тоғай",
      "қамыс","шалғын","жыра","аңғар","жар","үңгір","дөң","төбе","қыр",
      "жазық","ойпаң","белес","өткел","саға","арна","сел"},
     "Бұл сөз табиғатқа немесе географияға қатысты."),

    # ── Ауа райы ─────────────────────────────────────────────────
    ({"жел","қар","жаңбыр","бұлт","тұман","нөсер","боран","дауыл","жасын",
      "найзағай","мұз","шық","самал","леп","аяз","қырау","кемпірқосақ",
      "долы","ыстық","суық","жылу","нұр","жарық","бу","түтін"},
     "Бұл ауа райы немесе табиғат құбылысына қатысты."),

    # ── Өсімдіктер & Жемістер ────────────────────────────────────
    ({"шөп","гүл","терек","бұтақ","тамыр","жапырақ","жеміс","дән","тікен","мүк",
      "қайың","емен","шырша","арша","қарағай","тал","жусан","бетеге","сексеуіл",
      "алма","алмұрт","өрік","шабдалы","жүзім","қарбыз","қауын","жидек","бидай",
      "тары","арпа","күріш","жүгері","картоп","пияз","сәбіз","қырыққабат","қияр",
      "раушан","лале","нарцисс","қалампыр","долана","тобылғы","мойыл","итмұрын",
      "томат","сарымсақ","кәді","асқабақ","баклажан","жержаңғақ","соя",
      "зығыр","мақта","күнбағыс","таңқурай","шие"},
     "Бұл өсімдік, жеміс немесе дақылға қатысты сөз."),

    # ── Жануарлар & Құстар ───────────────────────────────────────
    ({"ат","жылқы","түйе","қой","сиыр","ешкі","ит","мысық","қоян","тышқан",
      "түлкі","қасқыр","аю","бұлан","марал","арыстан","барыс","жолбарыс",
      "бұғы","қабан","дельфин","кит","піл","зебра","жираф","маймыл",
      "тиін","кіртышқан","сусар","бұлғын","бобр","бұқа","торай","лақ",
      "бота","құлын","тайынша",
      "бүркіт","қыран","лашын","қаз","үйрек","аққу","тырна","дуадақ",
      "тауық","қораз","үкі","торғай","қарлығаш","кептер","тоқылдақ",
      "қарға","сауысқан","ителгі","сұңқар","бозторғай",
      "жылан","бақа","тасбақа","кесіртке","шаян","өрмекші",
      "құмырсқа","ара","шіркей","қоңыз","көбелек","шегіртке","маса","балық"},
     "Бұл жануар, хайуан немесе құс."),

    # ── Адам денесі ──────────────────────────────────────────────
    ({"бас","жүз","маңдай","қас","көз","мұрын","ауыз","ерін","тіс","тіл",
      "құлақ","мойын","иық","кеуде","арқа","бел","іш","қол","шынтақ",
      "білек","саусақ","аяқ","тізе","табан","шаш","сақал","мұрт","тырнақ",
      "жүрек","өкпе","бауыр","бүйрек","қан","сүйек","тері","дене",
      "омыртқа","бұлшықет","жүйке","тамыр","ми","асқазан","бүйрек үсті"},
     "Бұл адам денесінің мүшесі немесе дене бөлігі."),

    # ── Үй & Жиһаз ───────────────────────────────────────────────
    ({"үй","шаңырақ","есік","терезе","төбе","еден","қабырға","бөлме",
      "балкон","баспалдақ","қора","диірмен","қамал","пәтер","жатақхана",
      "кеңсе","зал","дәліз","аула","қоршау","дарбаза","қақпа","жертөле",
      "үстел","орындық","төсек","жастық","жабу","кілем","шам","айна",
      "сағат","кілт","жәшік","сандық","шелек","табақ","кесе","шыны",
      "қасық","шанышқы","пышақ","қазан","диван","кресло","шкаф","сөре","гардероб"},
     "Бұл үй немесе үй мүлкіне қатысты."),

    # ── Тамақ & Ішімдік ──────────────────────────────────────────
    ({"нан","ет","сорпа","бешбармақ","қазы","шұжық","сүт","айран","қымыз",
      "шай","кофе","май","тұз","қант","ұн","жұмыртқа","ірімшік","бал",
      "қаймақ","қуырдақ","манты","самса","борщ","палау","ботқа","тоқаш",
      "баурсақ","шелпек","жент","шырын","лимонад","морс","компот",
      "дәмдеуіш","бұрыш","сарымсақ","укроп","петрушка"},
     "Бұл тамақ немесе ішімдікке қатысты."),

    # ── Киім ─────────────────────────────────────────────────────
    ({"киім","көйлек","шалбар","жейде","пальто","шапан","бөрік","тымақ",
      "орамал","шарф","қолғап","белдік","етік","мәсі","тәпішке","туфля",
      "костюм","галстук","кофта","жилет","пуловер","свитер","жақа","тон"},
     "Бұл киім немесе киім-кешекке қатысты."),

    # ── Адам & Отбасы ────────────────────────────────────────────
    ({"ана","әке","бала","қыз","ұл","апа","аға","іні","қарындас","ата","әже",
      "немере","туыс","жесір","жар","күйеу","келін","дос","жау","көрші",
      "қонақ","жолаушы","батыр","хан","бек","би","адам","халық","отбасы",
      "нағашы","жиен","бөле","балдыз","қайнаға","жезде","ұрпақ","буын"},
     "Бұл адам немесе туыстық қарым-қатынасқа қатысты."),

    # ── Сезім & Рух ──────────────────────────────────────────────
    ({"жан","рух","сезім","ой","ақыл","арман","үміт","қайғы","қуаныш",
      "күлкі","жылау","ашу","қорқыныш","сенім","махаббат","сүйіспеншілік",
      "өкініш","рақым","мейір","намыс","ар","ұят","берекет","реніш",
      "ынта","ерік","талап","тілек","зейін","жады","қиял","шабыт","жігер",
      "бақыт","шындық","өтірік","жақсылық","жамандық","тағдыр"},
     "Бұл сезім, ой немесе рухани ұғым."),

    # ── Уақыт & Мезгіл ───────────────────────────────────────────
    ({"уақыт","жыл","ай","апта","күн","сағат","минут","секунд","таң","түс",
      "кеш","түн","бүгін","ертең","кеше","жаз","күз","қыс","көктем",
      "болашақ","өткен","мерзім","кезең","ғасыр","дәуір","заман","тоқсан"},
     "Бұл уақытқа немесе мезгілге қатысты."),

    # ── Білім & Мектеп ───────────────────────────────────────────
    ({"мектеп","сынып","сабақ","кітап","дәптер","қалам","тақта","мұғалім",
      "оқушы","студент","университет","ғылым","білім","зерттеу","тәжірибе",
      "гимназия","лицей","колледж","академия","зертхана","кітапхана",
      "мұражай","галерея","аудитория","емтихан","диплом","аттестат",
      "сертификат","реферат","диссертация","конспект","семинар","дәріс"},
     "Бұл білім немесе мектепке қатысты."),

    # ── Кәсіп & Жұмыс ────────────────────────────────────────────
    ({"жұмыс","еңбек","кәсіп","дәрігер","ұстаз","жазушы","ақын","суретші",
      "сатушы","бақташы","егінші","малшы","балықшы","аңшы","ұста","тігінші",
      "асшы","инженер","заңгер","экономист","бухгалтер","менеджер",
      "архитектор","дизайнер","программист","журналист","режиссер","актер",
      "хирург","терапевт","шаштараз","электрик","сантехник","жүргізуші",
      "аудармашы","тілмаш","редактор","диктор"},
     "Бұл кәсіп немесе мамандыққа қатысты."),

    # ── Қоғам & Мемлекет ─────────────────────────────────────────
    ({"мемлекет","халық","ұлт","отан","тарих","мәдениет","заң","құқық",
      "бостандық","бірлік","тәуелсіздік","бейбітшілік","соғыс","жеңіс",
      "саясат","сайлау","үкімет","парламент","президент","конституция",
      "армия","полиция","сот","депутат","прокурор","кодекс","жарғы"},
     "Бұл қоғам немесе мемлекетке қатысты."),

    # ── Дін & Дәстүр ─────────────────────────────────────────────
    ({"дін","намаз","мешіт","той","мереке","дәстүр","салт","ырым","дұға",
      "ораза","зекет","қажылық","жаназа","садақа","сенім","ғибадат",
      "пайғамбар","аят","шешен"},
     "Бұл дін немесе дәстүрге қатысты."),

    # ── Материалдар ──────────────────────────────────────────────
    ({"темір","алтын","күміс","мыс","тас","топырақ","құм","саз","ағаш",
      "май","су","от","жалын","түтін","күл","мұз","бу","болат","алюминий",
      "мырыш","қорғасын","платина","шойын","шыны","пластик","резеңке","мата"},
     "Бұл материал немесе заттық нәрсе."),

    # ── Көлік ────────────────────────────────────────────────────
    ({"жол","көше","машина","пойыз","ұшақ","кеме","велосипед","автобус",
      "трамвай","метро","такси","мотоцикл","арба","троллейбус","маршрутка",
      "трактор","комбайн","вертолет","зымыран","баржа","паром","яхта"},
     "Бұл көлік немесе жолсапарға қатысты."),

    # ── Технология & IT ──────────────────────────────────────────
    ({"телефон","компьютер","планшет","экран","интернет","бағдарлама",
      "сайт","код","алгоритм","деректер","принтер","сканер","монитор",
      "пернетақта","камера","микрофон","динамик","зарядтағыш","кабель",
      "робот","дрон","сервер","желі","қосымша"},
     "Бұл технология немесе IT-ге қатысты."),

    # ── Қаржы & Экономика ────────────────────────────────────────
    ({"ақша","банк","несие","депозит","пайыз","бюджет","нарық","сауда",
      "тауар","баға","жалақы","табыс","шығын","пайда","салық","инвестиция",
      "акция","облигация","биржа","валюта","қор","салым","шот"},
     "Бұл қаржы немесе экономикаға қатысты."),

    # ── Спорт ────────────────────────────────────────────────────
    ({"спорт","футбол","баскетбол","волейбол","теннис","бокс","күрес",
      "жүзу","жарыс","чемпионат","жеңімпаз","жүлде","медаль","стадион",
      "алаң","команда","тренер","турнир","финал","рекорд","кубок"},
     "Бұл спортқа қатысты."),

    # ── Медицина ─────────────────────────────────────────────────
    ({"аурухана","дәрі","операция","дәріхана","рецепт","диагноз","емдеу",
      "вакцина","қан","талдау","температура","қысым","жарақат","сынық",
      "жара","дерт","індет","эпидемия","терапия","хирургия","медбике"},
     "Бұл медицина немесе денсаулыққа қатысты."),

    # ── Өнер & Мәдениет ──────────────────────────────────────────
    ({"өнер","сурет","мүсін","кино","театр","музыка","би","өлең","жыр",
      "дастан","роман","повесть","әңгіме","пьеса","сценарий","палитра",
      "мозаика","графика","домбыра","қобыз","сыбызғы","дабыл","ән","әнші"},
     "Бұл өнер немесе мәдениетке қатысты."),

    # ── Абстрактілі ──────────────────────────────────────────────
    ({"өмір","өлім","туу","тіршілік","теңдік","шындық","өтірік","жақсылық",
      "жамандық","әділет","мән","мақсат","тағдыр","жазмыш","ерік",
      "рас","жалған","ақиқат","адалдық","парыз","міндет","мінез","қасиет"},
     "Бұл абстрактілі немесе философиялық ұғым."),
]

def _get_category_hint(word: str) -> str:
    for word_set, hint in _CATEGORIES:
        if word in word_set:
            return hint
    return "Бұл күнделікті өмірде жиі кездесетін сөз."


@app.get("/api/similar/{game_id}", tags=["game"])
async def get_similar_words(game_id: int):
    """Returns top 200 most similar words to the secret word. Only useful after winning."""
    if not engine.is_loaded():
        raise HTTPException(503, detail="Engine not ready.")
    secret = game_id_to_word(game_id)
    if not engine.word_exists(secret):
        raise HTTPException(500, detail="Secret word not in vocabulary.")
    similar = engine.get_top_similar(secret, topn=200)
    return {
        "secret": secret,
        "similar": [
            {"word": w, "rank": i + 2, "score": round(score, 4)}
            for i, (w, score) in enumerate(similar)
        ]
    }


@app.get("/api/similar/custom/{custom_token}", tags=["game"])
async def get_custom_similar(custom_token: str):
    """Returns top 200 similar words for a custom game."""
    if not engine.is_loaded():
        raise HTTPException(503, detail="Engine not ready.")
    secret = custom_games.get(custom_token)
    if not secret:
        raise HTTPException(404, detail="Custom game not found.")
    if not engine.word_exists(secret):
        raise HTTPException(500, detail="Secret word not in vocabulary.")
    similar = engine.get_top_similar(secret, topn=200)
    return {
        "secret": secret,
        "similar": [
            {"word": w, "rank": i + 2, "score": round(score, 4)}
            for i, (w, score) in enumerate(similar)
        ]
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
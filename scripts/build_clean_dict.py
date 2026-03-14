"""
build_clean_dict.py
===================
Қазақша таза сөздер сөздігін жасау.

3 дерек көзі:
1. Қазақ Wiktionary API — түбір сөздер
2. Біздің words.py — кураттелген тізім
3. Жиілік фильтрі — wiki.kk.vec-тен ең жиі кездесетін сөздер

Нәтиже:
    data/kk_clean_words.txt  — таза сөздер тізімі
    data/wiki.kk.filtered.vec — тек таза сөздердің векторлары

Іске қосу:
    cd ~/Downloads/zhasyrynsoz
    python3 scripts/build_clean_dict.py
"""

import urllib.request
import json
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

VECTORS_PATH  = Path("data/wiki.kk.vec")
OUTPUT_WORDS  = Path("data/kk_clean_words.txt")
OUTPUT_VEC    = Path("data/wiki.kk.filtered.vec")

# ── 1. Wiktionary-дан қазақ сөздерін алу ─────────────────────

def fetch_wiktionary_words(limit=5000):
    """Қазақ Wiktionary-дан зат есім, сын есім, етістік түбірлерін алу."""
    print("🌐 Wiktionary-дан сөздер жүктелуде...")
    
    words = set()
    url_template = (
        "https://kk.wiktionary.org/w/api.php?"
        "action=query&list=allpages&aplimit=500&apnamespace=0"
        "&apfrom={}&format=json&utf8=1"
    )
    
    apcontinue = ""
    fetched = 0
    
    while fetched < limit:
        url = url_template.format(urllib.parse.quote(apcontinue))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zhasyrynsoz-bot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            
            pages = data.get("query", {}).get("allpages", [])
            for page in pages:
                title = page["title"].lower().strip()
                # Тек қарапайым қазақ сөздері (арнайы беттерді алып тастаймыз)
                if is_clean_kazakh(title):
                    words.add(title)
            
            fetched += len(pages)
            print(f"   {fetched} бет өңделді, {len(words)} сөз табылды...")
            
            cont = data.get("query-continue", {}).get("allpages", {})
            if "apcontinue" in cont:
                apcontinue = cont["apcontinue"]
                time.sleep(0.5)  # API-ды шамадан тыс жүктемеу
            else:
                break
                
        except Exception as e:
            print(f"   ⚠️ Wiktionary қатесі: {e}")
            break
    
    print(f"   ✅ Wiktionary: {len(words)} сөз")
    return words


def fetch_wiktionary_simple():
    """Жылдам нұсқа — тек санаттар бойынша."""
    import urllib.parse
    
    print("🌐 Wiktionary санаттарынан сөздер жүктелуде...")
    words = set()
    
    # Негізгі санаттар
    categories = [
        "Қазақша_зат_есімдер",
        "Қазақша_сын_есімдер", 
        "Қазақша_етістіктер",
        "Қазақша_үстеулер",
        "Қазақша_есімдіктер",
    ]
    
    for cat in categories:
        url = (
            f"https://kk.wiktionary.org/w/api.php?"
            f"action=query&list=categorymembers&cmtitle=Category:{cat}"
            f"&cmlimit=500&format=json&utf8=1"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "zhasyrynsoz/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
            
            members = data.get("query", {}).get("categorymembers", [])
            for m in members:
                title = m["title"].lower().strip()
                if is_clean_kazakh(title):
                    words.add(title)
            
            print(f"   {cat}: {len(members)} сөз")
            time.sleep(0.3)
            
        except Exception as e:
            print(f"   ⚠️ {cat}: {e}")
    
    print(f"   ✅ Wiktionary санаттары: {len(words)} сөз")
    return words


# ── 2. Жалғауларды тексеру ────────────────────────────────────

BAD_CHARS = set('abcdefghijklmnopqrstuvwxyz0123456789@#$%^&*()[]{}|<>/\\"\',.:;!?')

# Жалғауларсыз болуы мүмкін — тек бұл жұрнақтармен аяқталса алып тастаймыз
INFLECTION_ENDINGS = [
    # Көптік
    "лар","лер","дар","дер","тар","тер",
    # Жатыс
    "да","де","та","те","нда","нде",
    # Шығыс  
    "дан","ден","тан","тен","нан","нен",
    # Табыс
    "ды","ді","ты","ті","ны","ні",
    # Барыс
    "ға","ге","қа","ке","на","не",
    # Ілік
    "ның","нің","дың","дің","тың","тің",
    # Көмектес
    "мен","бен","пен",
    # Тәуелдік
    "сы","сі","ым","ім","ың","іңіз","ыңыз",
    "імыз","ымыз","лары","лері",
    # Жіктік
    "мын","мін","сың","сің","ды","ді",
    "мыз","міз","сыздар","сіздер",
]

def is_clean_kazakh(word: str) -> bool:
    """Таза қазақ сөзі бе?"""
    w = word.lower().strip()
    if len(w) < 2 or len(w) > 20:
        return False
    if any(c in BAD_CHARS for c in w):
        return False
    # Цифр болмасын
    if any(c.isdigit() for c in w):
        return False
    return True


def looks_like_root(word: str, vocab_set: set) -> bool:
    """
    Сөз түбірге ұқсайды ма?
    Логика: жалғауын кескенде нәтиже сөздікте болса — жалғаулы форма.
    """
    w = word.lower()
    for ending in sorted(INFLECTION_ENDINGS, key=len, reverse=True):
        if w.endswith(ending):
            stem = w[:-len(ending)]
            if len(stem) >= 2 and stem in vocab_set:
                return False  # жалғаулы форма
    return True  # түбір форма


# ── 3. Негізгі логика ──────────────────────────────────────────

def load_vocab_fast(path):
    """Тек сөздер жиынын жүктеу."""
    vocab = set()
    with open(path, encoding="utf-8") as f:
        f.readline()
        for line in f:
            w = line.split(" ", 1)[0].lower()
            vocab.add(w)
    return vocab


def build_clean_dict():
    import urllib.parse
    
    if not VECTORS_PATH.exists():
        print(f"❌ {VECTORS_PATH} табылмады!")
        print("   Алдымен: ./scripts/download_vectors.sh")
        return

    # ── 1. words.py тізімі ──
    from words import DAILY_WORDS
    seed_words = set(w.lower() for w in DAILY_WORDS)
    print(f"✅ words.py: {len(seed_words)} seed сөз")

    # ── 2. Wiktionary ──
    wiki_words = fetch_wiktionary_simple()
    
    # ── 3. Vocab жүктеу ──
    print(f"\n📖 {VECTORS_PATH} сөздігі жүктелуде...")
    vocab_set = load_vocab_fast(VECTORS_PATH)
    print(f"   {len(vocab_set):,} сөз")

    # ── 4. Барлық дерек көздерін біріктіру ──
    all_candidates = seed_words | wiki_words
    
    # Тек vocab-та бар сөздерді қал
    in_vocab = {w for w in all_candidates if w in vocab_set}
    print(f"\n📊 Жиынтық: {len(in_vocab)} сөз vocab-та бар")

    # ── 5. Қосымша — жиілік бойынша таза сөздер ──
    # Vec файлынан алғашқы 50k сөзді алып, түбір формаларды қосамыз
    print(f"\n🔍 Vec файлынан жиі кездесетін таза сөздер іріктелуде...")
    freq_words = set()
    
    with open(VECTORS_PATH, encoding="utf-8") as f:
        f.readline()
        count = 0
        for line in f:
            if count >= 100000:
                break
            word = line.split(" ", 1)[0].lower()
            count += 1
            if is_clean_kazakh(word) and looks_like_root(word, vocab_set):
                freq_words.add(word)
    
    print(f"   Жиілік фильтрі: {len(freq_words)} таза сөз")
    
    # ── 6. Барлығын біріктіру ──
    final_words = in_vocab | freq_words
    final_words = {w for w in final_words if is_clean_kazakh(w)}
    
    # Жалғаулы формаларды алып тастау
    print(f"\n🧹 Жалғаулы формалар алынуда...")
    clean_final = {w for w in final_words if looks_like_root(w, vocab_set)}
    
    # seed_words әрқашан қалсын (біз қолмен тексердік)
    clean_final |= seed_words
    
    print(f"✅ Қорытынды таза сөздер: {len(clean_final):,}")

    # ── 7. Файлдарға жазу ──
    OUTPUT_WORDS.parent.mkdir(exist_ok=True)
    
    sorted_words = sorted(clean_final)
    with open(OUTPUT_WORDS, "w", encoding="utf-8") as f:
        for w in sorted_words:
            f.write(w + "\n")
    print(f"💾 {OUTPUT_WORDS}: {len(sorted_words)} сөз жазылды")

    # ── 8. Filtered vec жасау ──
    print(f"\n💾 {OUTPUT_VEC} жасалуда...")
    clean_set = set(sorted_words)
    
    written = 0
    lines_to_write = []
    
    with open(VECTORS_PATH, encoding="utf-8") as f:
        header = f.readline().strip()
        _, dim = header.split()
        for line in f:
            word = line.split(" ", 1)[0].lower()
            if word in clean_set:
                parts = line.rstrip().split(" ")
                parts[0] = word  # lowercase
                lines_to_write.append(" ".join(parts))
                written += 1
    
    with open(OUTPUT_VEC, "w", encoding="utf-8") as f:
        f.write(f"{written} {dim}\n")
        for line in lines_to_write:
            f.write(line + "\n")
    
    print(f"✅ {OUTPUT_VEC}: {written} сөз вектормен жазылды")
    print(f"\n📌 Келесі қадам — embeddings.py:")
    print(f"   VECTORS_PATH = './data/wiki.kk.filtered.vec'")


if __name__ == "__main__":
    build_clean_dict()

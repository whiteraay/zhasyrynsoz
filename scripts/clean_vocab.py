"""
clean_vocab.py
==============
wiki.kk.vec ішінен тек анық жалғаулы формаларды алып тастайды.
Логика: егер сөзді кескенде НӘТИЖЕ де сөздікте бар болса — жалғаулы форма.
Егер нәтиже сөздікте жоқ болса — бастапқы форма, қалдырамыз.

Іске қосу:
    cd ~/Downloads/zhasyrynsoz
    python3 scripts/clean_vocab.py

Нәтиже:
    data/wiki.kk.clean.vec
"""

from pathlib import Path

VECTORS_PATH = Path("data/wiki.kk.vec")
OUTPUT_VEC   = Path("data/wiki.kk.clean.vec")

# ── Жалғаулар тізімі (ұзыннан қысқаға) ──────────────────────
# Тек анық, нақты жалғаулар — қысқа жалғауларды қоспаймыз
# себебі олар түбірдің өзіне кіруі мүмкін

SUFFIXES = sorted([
    # Көптік
    "лардың", "лердің", "дардың", "дердің", "тардың", "тердің",
    "ларды",  "лерді",  "дарды",  "дерді",  "тарды",  "терді",
    "ларда",  "лерде",  "дарда",  "дерде",  "тарда",  "терде",
    "лардан", "лерден", "дардан", "дерден", "тардан", "терден",
    "ларға",  "лерге",  "дарға",  "дерге",  "тарға",  "терге",
    "лармен", "лермен", "дармен", "дермен", "тармен", "термен",
    "лары",   "лері",
    "лар",    "лер",    "дар",    "дер",    "тар",    "тер",

    # Септік (тек ұзын формалар — қысқаларды векторда тексереміз)
    "дікі",  "тікі",  "нікі",
    "дағы",  "дегі",  "тағы",  "тегі",
], key=len, reverse=True)

MIN_STEM = 3

def is_kazakh(word):
    bad = set("abcdefghijklmnopqrstuvwxyz0123456789@#$%^&*()[]{}|\\/<>")
    return not any(c in bad for c in word.lower()) and len(word) >= MIN_STEM

def load_vocab_set(path):
    """Тек сөздер жиынын жүктеу (векторсыз) — жылдам тексеру үшін."""
    print("📖 Сөздік жүктелуде (1-рет)...")
    vocab = set()
    with open(path, "r", encoding="utf-8") as f:
        f.readline()
        for line in f:
            word = line.split(" ", 1)[0]
            vocab.add(word)
    print(f"   {len(vocab):,} сөз жүктелді.")
    return vocab

def get_stem(word, vocab):
    """
    Жалғауды кес — бірақ тек нәтиже сөздікте болса.
    Егер нәтиже сөздікте жоқ болса — сөз өзі түбір.
    """
    w = word.lower()
    for suffix in SUFFIXES:
        if w.endswith(suffix):
            stem = w[:-len(suffix)]
            if len(stem) >= MIN_STEM and stem in vocab:
                return stem  # жалғаулы форма, кестік
    return w  # түбір форма, қалдырамыз

def clean_vectors():
    if not VECTORS_PATH.exists():
        print(f"❌ {VECTORS_PATH} табылмады!")
        return

    # 1. Сөздікті жиын ретінде жүктеу
    vocab_set = load_vocab_set(VECTORS_PATH)

    print(f"\n🧹 Тазалануда...")

    seen_stems = {}   # stem → vector_line
    total = kept = skipped = 0

    with open(VECTORS_PATH, "r", encoding="utf-8") as f:
        header = f.readline().strip()
        _, dim = header.split()

        for line in f:
            total += 1
            if total % 50000 == 0:
                print(f"   {total:,} өңделді, {kept:,} сақталды...")

            parts = line.rstrip().split(" ")
            if len(parts) < 5:
                continue

            word = parts[0]

            # Тек қазақша сөздер
            if not is_kazakh(word):
                skipped += 1
                continue

            # Түбірін тап
            stem = get_stem(word, vocab_set)

            # Бірінші кездескен немесе нақты түбір форма артық
            if stem not in seen_stems:
                seen_stems[stem] = line
                kept += 1
            else:
                # Егер бұл сөздің өзі = stem болса, векторын алмастыр
                if word.lower() == stem:
                    seen_stems[stem] = line

    print(f"\n✅ Нәтиже:")
    print(f"   Барлық сөз:    {total:,}")
    print(f"   Қазақ емес:    {skipped:,}")
    print(f"   Таза сөздер:   {kept:,}")

    # Жазу
    print(f"\n💾 {OUTPUT_VEC} жазылуда...")
    OUTPUT_VEC.parent.mkdir(exist_ok=True)

    with open(OUTPUT_VEC, "w", encoding="utf-8") as f:
        f.write(f"{kept} {dim}\n")
        for stem, line in seen_stems.items():
            # Бастапқы сөзді stem-ге алмастырып жазамыз
            parts = line.rstrip().split(" ")
            parts[0] = stem
            f.write(" ".join(parts) + "\n")

    print(f"✅ {OUTPUT_VEC} дайын!\n")
    print(f"📌 Келесі қадам — embeddings.py ішінде:")
    print(f"   VECTORS_PATH = './data/wiki.kk.clean.vec'")


def check_words():
    """words.py тізімін тексеру."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from words import DAILY_WORDS

    if not VECTORS_PATH.exists():
        print("❌ wiki.kk.vec жоқ, check мүмкін емес")
        return

    vocab_set = load_vocab_set(VECTORS_PATH)

    print(f"\n🔍 words.py тексерілуде ({len(DAILY_WORDS)} сөз)...")

    ok = []
    missing = []

    for word in DAILY_WORDS:
        if word in vocab_set:
            ok.append(word)
        else:
            missing.append(word)

    print(f"✅ Сөздікте бар:  {len(ok)}")
    if missing:
        print(f"⚠️  Сөздікте жоқ: {len(missing)}")
        for w in missing:
            print(f"   - {w}")
    else:
        print("🎉 Барлық сөз сөздікте бар!")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check_words()
    else:
        clean_vectors()
        check_words()
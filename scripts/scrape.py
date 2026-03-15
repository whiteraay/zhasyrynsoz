"""
clean_master.py
===============
kk_nouns_master.txt ішіндегі ағылшын/латын сөздерді тазалайды.
Тек қазақша кириллица сөздер қалады.

Іске қосу:
  python3 scripts/clean_master.py
"""

import re
from pathlib import Path

MASTER_FILE = Path("data/kk_nouns_master.txt")
REMOVED_FILE = Path("data/kk_nouns_removed.txt")  # не алынып тасталғанын көру үшін

def is_kazakh_cyrillic(word: str) -> bool:
    """
    Тек қазақша кириллица әріптерден тұратын сөздерді қабылдайды.
    Қазақ әліпбиі: стандартты орыс кирилл + ә і ң ғ ү ұ қ ө һ
    """
    return bool(re.match(r'^[а-яёәіңғүұқөһ\-]+$', word.lower()))

def main():
    if not MASTER_FILE.exists():
        print(f"❌ {MASTER_FILE} табылмады!")
        return

    lines = MASTER_FILE.read_text(encoding="utf-8").splitlines()
    total = len([l for l in lines if l.strip()])
    print(f"📌 Бастапқы сөз саны: {total:,}")

    kept = []
    removed = []

    for line in lines:
        word = line.strip().lower()
        if not word:
            continue
        if is_kazakh_cyrillic(word):
            kept.append(word)
        else:
            removed.append(word)

    # Тазаланған master файлын сақтау
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        for w in sorted(set(kept)):
            f.write(w + "\n")

    # Не алынды — тексеру үшін
    with open(REMOVED_FILE, "w", encoding="utf-8") as f:
        for w in sorted(set(removed)):
            f.write(w + "\n")

    print(f"✅ Қалған қазақша сөздер:  {len(set(kept)):,}")
    print(f"🗑️  Жойылған латын/ағылшын: {len(set(removed)):,}")
    print(f"📄 Не жойылғанын көру: {REMOVED_FILE}")
    print(f"\n📌 Енді apply_nouns.py-ді қайта іске қосыңыз:")
    print(f"   python3 scripts/apply_nouns.py")

if __name__ == "__main__":
    main()
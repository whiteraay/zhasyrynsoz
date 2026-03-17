"""
filter_vectors.py
=================
wiki.kk.vec-тен тек DAILY_WORDS-тағы сөздердің векторларын алады.
Docker build кезінде іске қосылады.

Нәтиже: /app/data/wiki.kk.filtered.vec  (тек 1197 сөз)
"""

import sys
from pathlib import Path

INPUT_VEC  = Path("/app/data/wiki.kk.vec")
OUTPUT_VEC = Path("/app/data/wiki.kk.filtered.vec")

# DAILY_WORDS жүктеу
sys.path.insert(0, "/app")
from words import DAILY_WORDS

daily_set = set(w.strip().lower() for w in DAILY_WORDS)
print(f"DAILY_WORDS: {len(daily_set)} сөз")

if not INPUT_VEC.exists():
    print(f"❌ {INPUT_VEC} жоқ!")
    sys.exit(1)

# Тек DAILY_WORDS-тағы векторларды сүз
matched = {}
with open(INPUT_VEC, "r", encoding="utf-8") as f:
    header = f.readline().strip().split()
    dim = int(header[1])
    for line in f:
        parts = line.rstrip().split(" ")
        if len(parts) != dim + 1:
            continue
        word = parts[0].strip().lower()
        if word in daily_set and word not in matched:
            parts[0] = word
            matched[word] = " ".join(parts)

print(f"Табылды: {len(matched)}/{len(daily_set)} сөз")

# Жоқ сөздер
missing = daily_set - set(matched.keys())
if missing:
    print(f"Векторда жоқ ({len(missing)}): {sorted(missing)[:20]}")

# Жазу
OUTPUT_VEC.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_VEC, "w", encoding="utf-8") as f:
    f.write(f"{len(matched)} {dim}\n")
    for line in matched.values():
        f.write(line + "\n")

print(f"✅ {OUTPUT_VEC}: {len(matched)} сөз жазылды")

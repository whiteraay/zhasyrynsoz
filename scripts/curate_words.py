"""
scripts/curate_words.py
========================
Utility to inspect, test, and expand the DAILY_WORDS list.

Usage:
    # Check that all daily words exist in the FastText vocabulary
    python scripts/curate_words.py check

    # Print the top-10 semantic neighbors for a given word
    python scripts/curate_words.py neighbors үй

    # Print today's and the next 7 days' scheduled words
    python scripts/curate_words.py schedule

    # Find words in the vocab matching a Kazakh prefix (useful for expanding the list)
    python scripts/curate_words.py search ат

Run from the project root:
    cd kazakhsho
    python scripts/curate_words.py check
"""

import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Allow importing backend modules
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from words import DAILY_WORDS, get_daily_word, EPOCH


def load_engine():
    """Load the embedding engine synchronously for script use."""
    import asyncio
    from embeddings import engine
    asyncio.run(engine.load())
    return engine


EPOCH_DATE = date(2024, 1, 1)


def cmd_check():
    print("Loading vectors (this may take a moment)...")
    engine = load_engine()

    missing = []
    present = []
    for word in DAILY_WORDS:
        if engine.word_exists(word):
            present.append(word)
        else:
            missing.append(word)

    print(f"\n✅  {len(present)}/{len(DAILY_WORDS)} words found in vocabulary")

    if missing:
        print(f"\n⚠️   {len(missing)} words NOT in vocabulary (will return 422 errors):")
        for w in missing:
            print(f"    - {w}")
        print("\nConsider replacing these words in backend/words.py")
    else:
        print("🎉  All words are in vocabulary — you're good to go!")


def cmd_neighbors(word):
    print(f"Loading vectors for '{word}'...")
    engine = load_engine()

    if not engine.word_exists(word):
        print(f"❌  '{word}' not found in vocabulary.")
        return

    neighbors = engine.get_top_similar(word, topn=20)
    print(f"\nTop 20 semantic neighbors for «{word}»:\n")
    for i, (w, score) in enumerate(neighbors, 1):
        bar = "█" * int(score * 30)
        print(f"  {i:2d}. {w:<20} {score:.4f}  {bar}")


def cmd_schedule():
    today = date.today()
    print(f"\nWord schedule (starting today, {today}):\n")
    print(f"  {'Day':>5}  {'Date':<12}  Word")
    print(f"  {'─'*5}  {'─'*12}  {'─'*20}")
    for i in range(14):
        d = today + timedelta(days=i)
        day_num = (d - EPOCH_DATE).days
        word = get_daily_word(day_num)
        marker = " ← today" if i == 0 else ""
        print(f"  {day_num:>5}  {str(d):<12}  {word}{marker}")


def cmd_search(prefix):
    print(f"Loading vectors to search prefix '{prefix}'...")
    engine = load_engine()

    matches = [w for w in engine.words if w.startswith(prefix)]
    matches.sort()

    print(f"\nFound {len(matches)} words starting with '{prefix}':\n")
    for w in matches[:60]:
        in_list = "✓" if w in set(DAILY_WORDS) else " "
        print(f"  [{in_list}] {w}")
    if len(matches) > 60:
        print(f"  ... and {len(matches) - 60} more")


def cmd_stats():
    print(f"\nWord list stats:")
    print(f"  Total daily words : {len(DAILY_WORDS)}")
    print(f"  Days of content   : {len(DAILY_WORDS)} (then repeats)")
    print(f"  Epoch date        : {EPOCH_DATE}")
    today = date.today()
    day_num = (today - EPOCH_DATE).days
    print(f"  Today's word #    : {day_num} → '{get_daily_word(day_num)}'")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "stats":
        cmd_stats()
    elif args[0] == "check":
        cmd_check()
    elif args[0] == "neighbors" and len(args) >= 2:
        cmd_neighbors(args[1])
    elif args[0] == "schedule":
        cmd_schedule()
    elif args[0] == "search" and len(args) >= 2:
        cmd_search(args[1])
    else:
        print(__doc__)

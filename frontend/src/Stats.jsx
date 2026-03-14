import { useMemo } from "react";

const HISTORY_KEY = "zhasyrynsoz_history";

export function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

export function saveGameToHistory(entry) {
  try {
    const history = loadHistory();
    // Avoid duplicates (same gameId + mode)
    const exists = history.find(
      (h) => h.gameId === entry.gameId && h.mode === entry.mode && h.customToken === entry.customToken
    );
    if (exists) return;
    history.push(entry);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch {}
}

export function clearHistory() {
  try { localStorage.removeItem(HISTORY_KEY); } catch {}
}

// ── Helpers ───────────────────────────────────────────────────

function medal(i) {
  return ["🥇", "🥈", "🥉"][i] || `${i + 1}.`;
}

function modeLabel(mode) {
  return { daily: "Күнделікті", random: "Кездейсоқ", custom: "Өз сөзім" }[mode] || mode;
}

function formatDate(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString("kk-KZ", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// ── Stats component ───────────────────────────────────────────

export default function Stats({ onClose }) {
  const history = loadHistory();

  const won = history.filter((h) => h.won);

  const stats = useMemo(() => {
    if (won.length === 0) return null;

    const guesses     = won.map((h) => h.guessCount);
    const avgGuesses  = (guesses.reduce((a, b) => a + b, 0) / guesses.length).toFixed(1);
    const totalPlayed = history.length;
    const totalWon    = won.length;
    const winRate     = Math.round((totalWon / totalPlayed) * 100);

    // Hardest = most guesses to win
    const hardest = [...won].sort((a, b) => b.guessCount - a.guessCount)[0];
    // Easiest = fewest guesses to win
    const easiest = [...won].sort((a, b) => a.guessCount - b.guessCount)[0];
    // Best streak
    let streak = 0, maxStreak = 0, cur = 0;
    history.forEach((h) => {
      if (h.won) { cur++; maxStreak = Math.max(maxStreak, cur); }
      else cur = 0;
    });
    // Current streak (from end)
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].won) streak++;
      else break;
    }

    // Guess distribution 1-10+
    const dist = {};
    won.forEach((h) => {
      const bucket = h.guessCount >= 10 ? "10+" : String(h.guessCount);
      dist[bucket] = (dist[bucket] || 0) + 1;
    });

    return { avgGuesses, totalPlayed, totalWon, winRate, hardest, easiest, streak, maxStreak, dist };
  }, [history]);

  const recent = [...history].reverse().slice(0, 10);

  return (
    <div className="stats-overlay" onClick={onClose}>
      <div className="stats-modal" onClick={(e) => e.stopPropagation()}>
        <div className="stats-header">
          <h2 className="stats-title">Статистика</h2>
          <button className="stats-close" onClick={onClose}>✕</button>
        </div>

        {history.length === 0 ? (
          <div className="stats-empty">
            <div className="stats-empty-icon">📊</div>
            <p>Әлі ойын жоқ.</p>
            <p>Бірінші ойынды ойнаңыз!</p>
          </div>
        ) : (
          <>
            {/* ── Summary cards ── */}
            {stats && (
              <div className="stats-cards">
                <div className="stat-card">
                  <strong>{stats.totalPlayed}</strong>
                  <span>Ойын</span>
                </div>
                <div className="stat-card">
                  <strong>{stats.winRate}%</strong>
                  <span>Жеңіс</span>
                </div>
                <div className="stat-card">
                  <strong>{stats.avgGuesses}</strong>
                  <span>Орт. болжам</span>
                </div>
                <div className="stat-card">
                  <strong>{stats.streak}</strong>
                  <span>Қатар жеңіс</span>
                </div>
              </div>
            )}

            {/* ── Hardest / Easiest ── */}
            {stats && (
              <div className="stats-extremes">
                <div className="extreme-card extreme-hard">
                  <div className="extreme-icon">🔥</div>
                  <div className="extreme-body">
                    <span className="extreme-label">Ең қиын</span>
                    <span className="extreme-word">{stats.hardest.secretWord || "—"}</span>
                    <span className="extreme-detail">{stats.hardest.guessCount} болжам · {formatDate(stats.hardest.ts)}</span>
                  </div>
                </div>
                <div className="extreme-card extreme-easy">
                  <div className="extreme-icon">⚡</div>
                  <div className="extreme-body">
                    <span className="extreme-label">Ең оңай</span>
                    <span className="extreme-word">{stats.easiest.secretWord || "—"}</span>
                    <span className="extreme-detail">{stats.easiest.guessCount} болжам · {formatDate(stats.easiest.ts)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* ── Guess distribution ── */}
            {stats && won.length > 0 && (
              <div className="stats-section">
                <div className="stats-section-title">Болжам саны бойынша үлестіру</div>
                <div className="dist-chart">
                  {["1","2","3","4","5","6","7","8","9","10+"].map((bucket) => {
                    const count = stats.dist[bucket] || 0;
                    const maxCount = Math.max(...Object.values(stats.dist));
                    const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    return (
                      <div key={bucket} className="dist-row">
                        <span className="dist-label">{bucket}</span>
                        <div className="dist-track">
                          <div className="dist-fill" style={{ width: `${pct}%` }} />
                        </div>
                        <span className="dist-count">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ── Recent games ── */}
            <div className="stats-section">
              <div className="stats-section-title">Соңғы ойындар</div>
              <div className="recent-list">
                {recent.map((h, i) => (
                  <div key={i} className={`recent-row ${h.won ? "recent-won" : "recent-lost"}`}>
                    <span className={`recent-result ${h.won ? "result-won" : "result-lost"}`}>
                      {h.won ? "✓" : "✗"}
                    </span>
                    <span className="recent-word">
                      {h.won ? (h.secretWord || "?") : "???"}
                    </span>
                    <span className="recent-mode">{modeLabel(h.mode)}</span>
                    <span className="recent-guesses">{h.guessCount} болжам</span>
                    <span className="recent-date">{formatDate(h.ts)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Clear button ── */}
            <button
              className="btn-clear-history"
              onClick={() => { clearHistory(); onClose(); }}
            >
              Тарихты өшіру
            </button>
          </>
        )}
      </div>
    </div>
  );
}

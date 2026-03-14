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

function formatDate(ts) {
  return new Date(ts).toLocaleDateString("kk-KZ", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function modeLabel(mode) {
  return { daily: "Күнделікті", random: "Кездейсоқ", custom: "Өз сөзім" }[mode] || mode;
}

// ── Share helpers ─────────────────────────────────────────────

function buildShareText(stats, history) {
  const won    = history.filter((h) => h.won);
  const latest = won[won.length - 1];
  if (!latest) return null;

  const bars = buildEmojiBar(latest.guessCount);
  return [
    "🇰🇿 Жасырын Сөз",
    `Сөз: ${"⬛".repeat(latest.secretWord?.length || 3)}`,
    `${latest.guessCount} болжаммен таптым!`,
    "",
    bars,
    "",
    `Жеңіс: ${stats.winRate}% | Орт: ${stats.avgGuesses} болжам`,
    "zhasyrynsoz.vercel.app",
  ].join("\n");
}

function buildEmojiBar(guessCount) {
  const colors = ["🟩","🟩","🟩","🟨","🟨","🟧","🟧","🟥","🟥","🟥"];
  return Array.from({ length: Math.min(guessCount, 10) }, (_, i) => colors[i] || "🟥").join("");
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

// ── Stats component ───────────────────────────────────────────

export default function Stats({ onClose }) {
  const history = loadHistory();
  const won     = history.filter((h) => h.won);

  const stats = useMemo(() => {
    if (won.length === 0) return null;
    const guesses    = won.map((h) => h.guessCount);
    const avgGuesses = (guesses.reduce((a, b) => a + b, 0) / guesses.length).toFixed(1);
    const winRate    = Math.round((won.length / history.length) * 100);
    const hardest    = [...won].sort((a, b) => b.guessCount - a.guessCount)[0];
    const easiest    = [...won].sort((a, b) => a.guessCount - b.guessCount)[0];

    let streak = 0;
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].won) streak++; else break;
    }
    let maxStreak = 0, cur = 0;
    history.forEach((h) => { if (h.won) { cur++; maxStreak = Math.max(maxStreak, cur); } else cur = 0; });

    const dist = {};
    won.forEach((h) => {
      const b = h.guessCount >= 10 ? "10+" : String(h.guessCount);
      dist[b] = (dist[b] || 0) + 1;
    });

    // Fun facts
    const avgBest = won.filter((h) => h.guessCount <= 5).length;
    const totalGuessesAllTime = won.reduce((s, h) => s + h.guessCount, 0);

    return { avgGuesses, winRate, hardest, easiest, streak, maxStreak, dist, avgBest, totalGuessesAllTime };
  }, [history]);

  const recent     = [...history].reverse().slice(0, 10);
  const shareText  = stats ? buildShareText(stats, history) : null;
  const [copied, setCopied] = [false, () => {}];

  const handleShare = async () => {
    if (!shareText) return;
    if (navigator.share) {
      try {
        await navigator.share({ title: "Жасырын Сөз", text: shareText, url: "https://zhasyrynsoz.vercel.app" });
        return;
      } catch {}
    }
    const ok = await copyToClipboard(shareText);
    if (ok) {
      // show feedback
      const btn = document.getElementById("share-btn");
      if (btn) { btn.textContent = "✓ Көшірілді!"; setTimeout(() => { btn.textContent = "📤 Бөлісу"; }, 2000); }
    }
  };

  const handleShareTwitter = () => {
    if (!shareText) return;
    const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}`;
    window.open(url, "_blank");
  };

  const handleShareWhatsApp = () => {
    if (!shareText) return;
    const url = `https://wa.me/?text=${encodeURIComponent(shareText)}`;
    window.open(url, "_blank");
  };

  const handleShareTelegram = () => {
    if (!shareText) return;
    const url = `https://t.me/share/url?url=https://zhasyrynsoz.vercel.app&text=${encodeURIComponent(shareText)}`;
    window.open(url, "_blank");
  };

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
            {/* Summary cards */}
            {stats && (
              <div className="stats-cards">
                <div className="stat-card">
                  <strong>{history.length}</strong><span>Ойын</span>
                </div>
                <div className="stat-card">
                  <strong>{stats.winRate}%</strong><span>Жеңіс</span>
                </div>
                <div className="stat-card">
                  <strong>{stats.avgGuesses}</strong><span>Орт. болжам</span>
                </div>
                <div className="stat-card">
                  <strong>{stats.streak} 🔥</strong><span>Қатар жеңіс</span>
                </div>
              </div>
            )}

            {/* Fun facts */}
            {stats && (
              <div className="fun-facts">
                <div className="fun-fact">
                  <span className="ff-icon">⚡</span>
                  <span className="ff-text">5-тен аз болжаммен: <strong>{stats.avgBest} рет</strong></span>
                </div>
                <div className="fun-fact">
                  <span className="ff-icon">🎯</span>
                  <span className="ff-text">Барлық болжам: <strong>{stats.totalGuessesAllTime}</strong></span>
                </div>
                <div className="fun-fact">
                  <span className="ff-icon">🏆</span>
                  <span className="ff-text">Ең ұзын серия: <strong>{stats.maxStreak} жеңіс</strong></span>
                </div>
              </div>
            )}

            {/* Hardest / Easiest */}
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

            {/* Guess distribution */}
            {stats && (
              <div className="stats-section">
                <div className="stats-section-title">Болжам үлестіруі</div>
                <div className="dist-chart">
                  {["1","2","3","4","5","6","7","8","9","10+"].map((b) => {
                    const count    = stats.dist[b] || 0;
                    const maxCount = Math.max(...Object.values(stats.dist));
                    const pct      = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    return (
                      <div key={b} className="dist-row">
                        <span className="dist-label">{b}</span>
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

            {/* Share section */}
            {shareText && (
              <div className="share-section">
                <div className="stats-section-title">Досыңызбен бөлісіңіз!</div>
                <div className="share-preview">{shareText}</div>
                <div className="share-buttons">
                  <button id="share-btn" className="share-btn share-copy" onClick={handleShare}>
                    📤 Бөлісу
                  </button>
                  <button className="share-btn share-telegram" onClick={handleShareTelegram}>
                    ✈️ Telegram
                  </button>
                  <button className="share-btn share-whatsapp" onClick={handleShareWhatsApp}>
                    💬 WhatsApp
                  </button>
                  <button className="share-btn share-twitter" onClick={handleShareTwitter}>
                    𝕏 Twitter
                  </button>
                </div>
              </div>
            )}

            {/* Recent games */}
            <div className="stats-section">
              <div className="stats-section-title">Соңғы ойындар</div>
              <div className="recent-list">
                {recent.map((h, i) => (
                  <div key={i} className={`recent-row ${h.won ? "recent-won" : "recent-lost"}`}>
                    <span className={`recent-result ${h.won ? "result-won" : "result-lost"}`}>
                      {h.won ? "✓" : "✗"}
                    </span>
                    <span className="recent-word">{h.won ? (h.secretWord || "?") : "???"}</span>
                    <span className="recent-mode">{modeLabel(h.mode)}</span>
                    <span className="recent-guesses">{h.guessCount} болжам</span>
                    <span className="recent-date">{formatDate(h.ts)}</span>
                  </div>
                ))}
              </div>
            </div>

            <button className="btn-clear-history" onClick={() => { clearHistory(); onClose(); }}>
              Тарихты өшіру
            </button>
          </>
        )}
      </div>
    </div>
  );
}

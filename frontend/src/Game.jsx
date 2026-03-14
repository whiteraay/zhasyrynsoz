import { useState, useEffect, useRef, useCallback } from "react";
import {
  fetchDailyGame, fetchRandomGame, createCustomGame,
  submitGuess, fetchHint, APIError,
} from "./api";
import { saveGameToHistory } from "./Stats";

// ── LocalStorage ──────────────────────────────────────────────
const STORAGE_KEY = "zhasyrynsoz_v2";

function loadState(gameId) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw);
    if (p.gameId !== gameId) return null;
    return p;
  } catch { return null; }
}

function saveState(gameId, guesses, won) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ gameId, guesses, won }));
  } catch {}
}

// ── Helpers ───────────────────────────────────────────────────
function rankLabel(rank) {
  return rank === 1 ? "1" : rank.toLocaleString();
}

function barWidth(rank) {
  if (rank === 1) return 100;
  const maxRank = 200000;
  const pct = (1 - Math.log10(Math.min(rank, maxRank)) / Math.log10(maxRank)) * 100;
  return Math.max(2, Math.round(pct * 10) / 10);
}

function barClass(color) {
  return { winner: "bar-winner", hot: "bar-green", warm: "bar-orange", cold: "bar-pink" }[color] || "bar-pink";
}

// ── GuessItem ─────────────────────────────────────────────────
function GuessItem({ guess, rank, color, isLatest }) {
  return (
    <div className={`guess-row ${isLatest ? "guess-latest" : ""}`}>
      <span className={`guess-word-label ${barClass(color)}-text`}>{guess}</span>
      <div className="guess-bar-track">
        <div className={`guess-bar-fill ${barClass(color)}`} style={{ width: `${barWidth(rank)}%` }} />
      </div>
      <span className="guess-bar-rank">{rankLabel(rank)}</span>
    </div>
  );
}

// ── Hint config ───────────────────────────────────────────────
const MAX_HINTS       = 5;   // max for non-close_word hints
const MAX_CLOSE_WORD  = 10;  // close_word can be used up to 10 times

const HINTS = [
  { type: "category",   icon: "◈", label: "Санат",     sublabel: "Қандай топ?",   color: "#a78bfa" },
  { type: "letter",     icon: "А", label: "1-ші әріп", sublabel: "Басталуы",      color: "#34d399" },
  { type: "length",     icon: "⟷", label: "Ұзындық",   sublabel: "Нешe әріп?",    color: "#60a5fa" },
  { type: "far_word",   icon: "○", label: "Алыс сөз",  sublabel: "~200–300 орын", color: "#f87171" },
  { type: "mid_word",   icon: "◎", label: "Орта сөз",  sublabel: "~50–80 орын",   color: "#fb923c" },
  { type: "close_word", icon: "●", label: "Жақын сөз", sublabel: "~20–30 орын",   color: "#4ade80" },
];

// ── Main Game ─────────────────────────────────────────────────
export default function Game() {
  const [gameId, setGameId]               = useState(null);
  const [customToken, setCustomToken]     = useState(null);
  const [gameMode, setGameMode]           = useState("daily");
  const [guesses, setGuesses]             = useState([]);
  const [won, setWon]                     = useState(false);
  const [input, setInput]                 = useState("");
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState("");
  const [showCustomForm, setShowCustomForm] = useState(false);
  const [customInput, setCustomInput]     = useState("");
  const [customLoading, setCustomLoading] = useState(false);
  const [customError, setCustomError]     = useState("");
  const [sortByRank, setSortByRank]       = useState(false);
  const [latestGuess, setLatestGuess]     = useState(null);
  const [hintStates, setHintStates]       = useState({});
  const [showHints, setShowHints]         = useState(false);
  const inputRef = useRef(null);

  // ── Init ──────────────────────────────────────
  useEffect(() => {
    fetchDailyGame()
      .then((d) => {
        setGameId(d.game_id);
        const saved = loadState(d.game_id);
        if (saved) { setGuesses(saved.guesses); setWon(saved.won); }
      })
      .catch(() => showError("Серверге қосылу мүмкін болмады."));
  }, []);

  useEffect(() => {
    if (gameId !== null && gameMode !== "custom") saveState(gameId, guesses, won);
  }, [gameId, guesses, won, gameMode]);

  // ── Derived ───────────────────────────────────
  const bestRank    = guesses.reduce((b, g) => (g.rank < b ? g.rank : b), Infinity);
  const bestDisplay = guesses.length === 0 ? "—" : bestRank === 1 ? "★" : bestRank.toLocaleString();

  const displayGuesses = sortByRank
    ? [...guesses].sort((a, b) => a.rank - b.rank)
    : [...guesses].reverse();

  // Count non-close_word hints used
  const regularHintsUsed = HINTS
    .filter((h) => h.type !== "close_word")
    .filter((h) => !!hintStates[h.type]?.result)
    .length;

  // ── Error helper ──────────────────────────────
  function showError(msg, ms = 3000) {
    setError(msg);
    setTimeout(() => setError(""), ms);
  }

  // ── Guess ─────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    const word = input.trim().toLowerCase();
    if (!word || loading || won) return;
    if (guesses.find((g) => g.guess === word)) {
      showError("Бұл сөзді бұрын болжадыңыз.");
      setInput("");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await submitGuess(gameId, word, customToken);
      const entry = {
        guess:         result.guess,
        rank:          result.rank,
        color:         result.color,
        closeness_pct: result.closeness_pct,
      };
      setGuesses((prev) => [...prev, entry]);
      setLatestGuess(result.guess);
      setTimeout(() => setLatestGuess(null), 1500);
      setInput("");
      if (result.found) {
        setWon(true);
        saveGameToHistory({
          gameId:      gameId,
          customToken: customToken || null,
          mode:        gameMode,
          won:         true,
          guessCount:  guesses.length + 1,
          secretWord:  result.guess,
          ts:          Date.now(),
        });
      }
    } catch (err) {
      if (err instanceof APIError && err.code === "WORD_NOT_FOUND") {
        showError(`«${word}» — сөздікте жоқ.`);
      } else {
        showError(err.message || "Қате орын алды.");
      }
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, won, guesses, gameId, customToken, gameMode]);

  // ── Mode switches ─────────────────────────────
  const switchToDaily = async () => {
    const d = await fetchDailyGame();
    setGameId(d.game_id); setCustomToken(null); setGameMode("daily");
    setGuesses([]); setWon(false); setHintStates({}); setShowCustomForm(false);
  };

  const switchToRandom = async () => {
    const d = await fetchRandomGame();
    setGameId(d.game_id); setCustomToken(null); setGameMode("random");
    setGuesses([]); setWon(false); setHintStates({}); setShowCustomForm(false);
  };

  const handleCreateCustom = async () => {
    const word = customInput.trim().toLowerCase();
    if (!word) return;
    setCustomLoading(true);
    setCustomError("");
    try {
      const result = await createCustomGame(word);
      setCustomToken(result.custom_token); setGameId(null); setGameMode("custom");
      setGuesses([]); setWon(false); setHintStates({});
      setCustomInput(""); setShowCustomForm(false);
    } catch (err) {
      setCustomError(err.message || "Сөз қабылданмады.");
    } finally {
      setCustomLoading(false);
    }
  };

  // ── Hints ─────────────────────────────────────
  const handleHint = useCallback(async (type) => {
    if (hintStates[type]?.loading) return;

    // ── close_word: up to MAX_CLOSE_WORD times, each gives new word ──
    if (type === "close_word") {
      const prev  = hintStates[type] || { results: [], count: 0 };
      if (prev.count >= MAX_CLOSE_WORD) return;
      setHintStates((s) => ({ ...s, [type]: { ...prev, loading: true } }));
      try {
        const result = await fetchHint(gameId, type, customToken, prev.count);
        setHintStates((s) => ({
          ...s,
          [type]: {
            loading: false,
            count:   prev.count + 1,
            results: [...(prev.results || []), result.hint],
            result:  result.hint,
          },
        }));
      } catch {
        setHintStates((s) => ({ ...s, [type]: { ...prev, loading: false } }));
      }
      return;
    }

    // ── All other hints: one-time, limited to MAX_HINTS total ──
    if (hintStates[type]?.result) return;
    if (regularHintsUsed >= MAX_HINTS) return;
    setHintStates((s) => ({ ...s, [type]: { loading: true } }));
    try {
      const result = await fetchHint(gameId, type, customToken);
      setHintStates((s) => ({ ...s, [type]: { loading: false, result: result.hint } }));
    } catch {
      setHintStates((s) => ({ ...s, [type]: { loading: false } }));
    }
  }, [hintStates, regularHintsUsed, gameId, customToken]);

  // ── Render ────────────────────────────────────
  return (
    <div className="game-wrap">

      {/* Mode selector */}
      <div className="mode-bar">
        <button className={`mode-btn ${gameMode === "daily"  ? "mode-active" : ""}`} onClick={switchToDaily}>Күнделікті</button>
        <button className={`mode-btn ${gameMode === "random" ? "mode-active" : ""}`} onClick={switchToRandom}>Кездейсоқ 🎲</button>
        <button className={`mode-btn ${gameMode === "custom" ? "mode-active" : ""}`} onClick={() => setShowCustomForm((v) => !v)}>Өз сөзім ✏️</button>
      </div>

      {/* Custom word form */}
      {showCustomForm && (
        <div className="custom-form">
          <p className="custom-title">Жасырын сөзді енгізіңіз</p>
          <div className="input-row">
            <input
              className="guess-input"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateCustom()}
              placeholder="Мысалы: үй, жылқы, арман..."
              autoComplete="off" spellCheck={false}
            />
            <button className="btn-submit" onClick={handleCreateCustom} disabled={customLoading || !customInput.trim()}>
              {customLoading ? "…" : "Бастау"}
            </button>
          </div>
          {customError && <div className="error-msg">{customError}</div>}
          <p className="custom-hint">Сөзді енгізіп, досыңызбен ойнаңыз!</p>
        </div>
      )}

      {/* Top bar */}
      <div className="top-bar">
        <span className="top-guesses">
          БОЛЖАМДАР: <strong>{guesses.length}</strong>
          {guesses.length > 0 && <span className="top-best"> · Жақын: <strong>{bestDisplay}</strong></span>}
        </span>
        <div className="top-controls">
          {guesses.length > 1 && (
            <button className={`ctrl-btn ${sortByRank ? "ctrl-active" : ""}`} onClick={() => setSortByRank((v) => !v)}>
              {sortByRank ? "↕ Уақыт" : "↕ Нөмір"}
            </button>
          )}
          <button className={`ctrl-btn ${showHints ? "ctrl-active" : ""}`} onClick={() => setShowHints((v) => !v)}>
            Кеңес {showHints ? "▲" : "▼"}
          </button>
        </div>
      </div>

      {/* Input */}
      <div className="input-row">
        <input
          ref={inputRef}
          className="guess-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          placeholder="Сөз жазыңыз..."
          disabled={loading || won || (gameId === null && !customToken)}
          autoComplete="off" autoCorrect="off" spellCheck={false}
        />
        <button
          className="btn-submit"
          onClick={handleSubmit}
          disabled={loading || won || !input.trim() || (gameId === null && !customToken)}
        >
          {loading ? "…" : "Болжау"}
        </button>
      </div>

      {error && <div className="error-msg">{error}</div>}

      {/* Hints panel */}
      {showHints && (
        <div className="hints-panel">
          <div className="hints-used-label">
            <span>Кеңестер</span>
            <span className={regularHintsUsed >= MAX_HINTS ? "hints-limit-reached" : ""}>
              {regularHintsUsed}/{MAX_HINTS} пайдаланылды
            </span>
          </div>

          <div className="hints-grid">
            {HINTS.map((h) => {
              const state = hintStates[h.type] || {};
              const busy  = !!state.loading;

              /* ── close_word — special multi-use card ── */
              if (h.type === "close_word") {
                const count   = state.count || 0;
                const results = state.results || [];
                const maxed   = count >= MAX_CLOSE_WORD;
                return (
                  <div
                    key={h.type}
                    className={`hint-card hint-card-wide ${busy ? "hint-busy" : ""} ${maxed ? "hint-locked" : ""}`}
                    style={{ "--hc": h.color }}
                    onClick={() => !busy && !maxed && handleHint(h.type)}
                  >
                    <span className="hc-icon" style={{ color: count > 0 ? h.color : maxed ? "#2d3748" : "#4a5568" }}>
                      {maxed ? "🔒" : h.icon}
                    </span>
                    <div className="hc-body" style={{ flex: 1 }}>
                      <div className="hc-top-row">
                        <span className="hc-label">{h.label}</span>
                        <span className={`hc-counter ${maxed ? "hc-counter-maxed" : ""}`}>
                          {count}/{MAX_CLOSE_WORD}
                        </span>
                      </div>
                      {results.length === 0 ? (
                        <span className="hc-sub">{busy ? "…" : h.sublabel}</span>
                      ) : (
                        <div className="close-words-list">
                          {results.map((r, i) => (
                            <span key={i} className="close-word-badge">
                              {r.match(/«(.+)»/)?.[1] || r}
                            </span>
                          ))}
                          {!maxed && !busy && (
                            <span className="close-word-more">+ тағы</span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              }

              /* ── regular one-time hints ── */
              const used   = !!state.result;
              const locked = !used && regularHintsUsed >= MAX_HINTS;
              return (
                <div
                  key={h.type}
                  className={`hint-card ${used ? "hint-used" : ""} ${busy ? "hint-busy" : ""} ${locked ? "hint-locked" : ""}`}
                  onClick={() => !used && !busy && !locked && handleHint(h.type)}
                  style={{ "--hc": h.color }}
                >
                  <span className="hc-icon" style={{ color: used ? h.color : locked ? "#2d3748" : "#4a5568" }}>
                    {locked ? "🔒" : h.icon}
                  </span>
                  <div className="hc-body">
                    <span className="hc-label" style={{ color: locked ? "var(--text-dim)" : undefined }}>{h.label}</span>
                    <span className="hc-sub">{busy ? "…" : used ? state.result : locked ? "Лимит" : h.sublabel}</span>
                  </div>
                  {used && <span className="hc-tick" style={{ color: h.color }}>✓</span>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Win banner */}
      {won && (
        <div className="win-banner">
          <span className="win-icon">🏆</span>
          <div>
            <div className="win-title">Керемет!</div>
            <div className="win-sub">{guesses.length} болжаммен таптыңыз!</div>
          </div>
          <button className="btn-new-game" onClick={gameMode === "random" ? switchToRandom : switchToDaily}>
            Жаңа ойын
          </button>
        </div>
      )}

      {/* Guess bars */}
      {guesses.length > 0 && (
        <div className="guess-list">
          {displayGuesses.map((g) => (
            <GuessItem key={g.guess} {...g} isLatest={g.guess === latestGuess} />
          ))}
        </div>
      )}

    </div>
  );
}

import { createContext, useContext, useState, useEffect } from "react";

const THEME_KEY = "zhasyrynsoz_theme";

export const themes = [
  {
    id: "dark",
    label: "Қараңғы",
    emoji: "🌙",
    vars: {
      "--bg":           "#0d1520",
      "--bg2":          "#111927",
      "--bg3":          "#192030",
      "--border":       "rgba(255,255,255,0.08)",
      "--text":         "#e2e8f0",
      "--text-muted":   "#64748b",
      "--text-dim":     "#334155",
      "--bar-track":    "rgba(255,255,255,0.05)",
      "--overlay":      "rgba(0,0,0,0.7)",
    },
  },
  {
    id: "light",
    label: "Жарық",
    emoji: "☀️",
    vars: {
      "--bg":           "#f8fafc",
      "--bg2":          "#ffffff",
      "--bg3":          "#f1f5f9",
      "--border":       "rgba(0,0,0,0.10)",
      "--text":         "#0f172a",
      "--text-muted":   "#64748b",
      "--text-dim":     "#94a3b8",
      "--bar-track":    "rgba(0,0,0,0.06)",
      "--overlay":      "rgba(0,0,0,0.5)",
    },
  },
  {
    id: "steppe",
    label: "Дала",
    emoji: "🌾",
    vars: {
      "--bg":           "#1a1208",
      "--bg2":          "#221a0a",
      "--bg3":          "#2e2410",
      "--border":       "rgba(201,168,76,0.18)",
      "--text":         "#ede8d8",
      "--text-muted":   "#8a8270",
      "--text-dim":     "#504c40",
      "--bar-track":    "rgba(201,168,76,0.08)",
      "--overlay":      "rgba(0,0,0,0.75)",
    },
    accent: "#C9A84C",
  },
  {
    id: "night",
    label: "Түнгі көк",
    emoji: "🌌",
    vars: {
      "--bg":           "#060b18",
      "--bg2":          "#0a1020",
      "--bg3":          "#0f172a",
      "--border":       "rgba(99,179,237,0.15)",
      "--text":         "#e2e8f0",
      "--text-muted":   "#4a6fa5",
      "--text-dim":     "#1e3a5f",
      "--bar-track":    "rgba(99,179,237,0.06)",
      "--overlay":      "rgba(0,0,0,0.8)",
    },
    accent: "#63b3ed",
  },
  {
    id: "forest",
    label: "Орман",
    emoji: "🌲",
    vars: {
      "--bg":           "#0a1a0e",
      "--bg2":          "#0f2213",
      "--bg3":          "#162d1a",
      "--border":       "rgba(74,222,128,0.15)",
      "--text":         "#dcfce7",
      "--text-muted":   "#4a7c59",
      "--text-dim":     "#1a3d26",
      "--bar-track":    "rgba(74,222,128,0.07)",
      "--overlay":      "rgba(0,0,0,0.75)",
    },
    accent: "#4ade80",
  },
  {
    id: "sunset",
    label: "Күн батыс",
    emoji: "🌅",
    vars: {
      "--bg":           "#1a0a05",
      "--bg2":          "#221008",
      "--bg3":          "#2e160a",
      "--border":       "rgba(251,146,60,0.18)",
      "--text":         "#fff7ed",
      "--text-muted":   "#92400e",
      "--text-dim":     "#431407",
      "--bar-track":    "rgba(251,146,60,0.08)",
      "--overlay":      "rgba(0,0,0,0.75)",
    },
    accent: "#fb923c",
  },
];

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [themeId, setThemeId] = useState(() => {
    try { return localStorage.getItem(THEME_KEY) || "dark"; } catch { return "dark"; }
  });

  const theme = themes.find((t) => t.id === themeId) || themes[0];

  useEffect(() => {
    const root = document.documentElement;
    Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    // accent color for gold/links
    if (theme.accent) root.style.setProperty("--gold", theme.accent);
    else root.style.setProperty("--gold", "#eab308");
    try { localStorage.setItem(THEME_KEY, themeId); } catch {}
  }, [themeId, theme]);

  return (
    <ThemeContext.Provider value={{ themeId, setThemeId, theme, themes }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}

// ── Theme picker modal ────────────────────────────────────────

export function ThemePicker({ onClose }) {
  const { themeId, setThemeId } = useTheme();

  return (
    <div className="stats-overlay" onClick={onClose}>
      <div className="stats-modal theme-modal" onClick={(e) => e.stopPropagation()}>
        <div className="stats-header">
          <h2 className="stats-title">Тақырып таңдаңыз</h2>
          <button className="stats-close" onClick={onClose}>✕</button>
        </div>
        <div className="theme-grid">
          {themes.map((t) => (
            <button
              key={t.id}
              className={`theme-card ${themeId === t.id ? "theme-card-active" : ""}`}
              onClick={() => { setThemeId(t.id); onClose(); }}
            >
              <div
                className="theme-preview"
                style={{
                  background: t.vars["--bg"],
                  border: `2px solid ${t.vars["--border"]}`,
                }}
              >
                <div className="tp-bar1" style={{ background: t.accent || "#eab308", width: "70%" }} />
                <div className="tp-bar2" style={{ background: t.accent ? t.accent + "80" : "#22c55e80", width: "45%" }} />
                <div className="tp-bar3" style={{ background: t.accent ? t.accent + "40" : "#f9731640", width: "25%" }} />
              </div>
              <div className="theme-label">
                <span className="theme-emoji">{t.emoji}</span>
                <span>{t.label}</span>
              </div>
              {themeId === t.id && <span className="theme-check">✓</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

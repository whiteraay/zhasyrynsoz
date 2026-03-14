import { useState } from "react";
import Game from "./Game";
import Stats from "./Stats";
import { ThemeProvider, ThemePicker } from "./Theme";
import "./index.css";

function AppInner() {
  const [showRules, setShowRules] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showTheme, setShowTheme] = useState(false);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-logo">
          <h1 className="app-title">ЖАСЫРЫН СӨЗ</h1>
          <div className="app-infinity">∞</div>
        </div>
        <div className="header-btns">
          <button className="btn-icon" onClick={() => setShowStats(true)}  title="Статистика">📊</button>
          <button className="btn-icon" onClick={() => setShowTheme(true)}  title="Тақырып">🎨</button>
          <button className="btn-rules" onClick={() => setShowRules((v) => !v)}>{showRules ? "✕" : "?"}</button>
        </div>
      </header>

      {showRules && (
        <div className="rules-panel">
          <h3>Қалай ойнауға болады?</h3>
          <ol>
            <li>Жасырын <strong>қазақ сөзін</strong> табуыңыз керек.</li>
            <li>Кез келген сөзді жазып, <strong>Болжау</strong> батырмасын басыңыз.</li>
            <li>Болжамыңыздың <strong>мағыналық жақындығы</strong> нөмір түрінде шығады.</li>
            <li><span className="rule-hot">1–99</span> = өте жақын, <span className="rule-warm">100–999</span> = жақын, <span className="rule-cold">1000+</span> = алыс.</li>
            <li>Нөмір <strong>1</strong> болса — таптыңыз! 🎉</li>
          </ol>
        </div>
      )}

      <main className="app-main">
        <Game />
      </main>

      <footer className="app-footer">
        <p>Жасырын Сөз · Қазақша мағыналық ойын</p>
      </footer>

      {showStats && <Stats onClose={() => setShowStats(false)} />}
      {showTheme && <ThemePicker onClose={() => setShowTheme(false)} />}
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  );
}

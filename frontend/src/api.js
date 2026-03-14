const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    const msg =
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.message || "Қате орын алды.";
    throw new APIError(msg, data.detail?.code || "API_ERROR", res.status);
  }
  return data;
}

export class APIError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code   = code;
    this.status = status;
  }
}

export async function fetchDailyGame() {
  return apiFetch("/api/daily");
}

export async function fetchRandomGame() {
  return apiFetch("/api/random");
}

export async function createCustomGame(word) {
  return apiFetch("/api/custom", {
    method: "POST",
    body: JSON.stringify({ word }),
  });
}

export async function submitGuess(gameId, guess, customToken = null) {
  return apiFetch("/api/guess", {
    method: "POST",
    body: JSON.stringify({
      ...(customToken ? { custom_token: customToken } : { game_id: gameId }),
      guess,
    }),
  });
}

// offset only used for close_word — each call gets a different word
export async function fetchHint(gameId, hintType = "category", customToken = null, offset = 0) {
  if (customToken) {
    return apiFetch(`/api/hint/custom/${customToken}?hint_type=${hintType}&offset=${offset}`);
  }
  return apiFetch(`/api/hint/${gameId}?hint_type=${hintType}&offset=${offset}`);
}

/**
 * Fetch top 60 similar words after winning.
 */
export async function fetchSimilarWords(gameId, customToken = null) {
  if (customToken) {
    return apiFetch(`/api/similar/custom/${customToken}`);
  }
  return apiFetch(`/api/similar/${gameId}`);
}

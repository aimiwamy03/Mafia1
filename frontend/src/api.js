async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || res.statusText || "Request failed");
  }
  return data;
}

export const api = {
  startGame: () => request("/api/game/start", { method: "POST" }),
  gameState: () => request("/api/game/state"),
  vote: (target, voter = "You") =>
    request("/api/game/vote", { method: "POST", body: JSON.stringify({ voter, target }) }),
  photograph: (prompt) =>
    request("/api/store/photography", { method: "POST", body: JSON.stringify({ prompt }) }),
  postOffice: (message) =>
    request("/api/store/postoffice", { method: "POST", body: JSON.stringify({ message }) }),
  bank: () => request("/api/store/bank", { method: "POST" }),
  library: (question) =>
    request("/api/store/library", { method: "POST", body: JSON.stringify({ question }) }),
};

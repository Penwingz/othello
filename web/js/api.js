// Small client for the local JSON API: calls return parsed JSON or throw ApiError.

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can't reach the game server. Is python -m othello still running?");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (${response.status}).`;
    throw new ApiError(response.status, detail);
  }
  return data;
}

const game_Path = (id) => `/api/games/${encodeURIComponent(id)}`;

export const api = {
  engines: () => request("GET", "/api/engines"),
  engine_Errors: () => request("GET", "/api/engines/errors"),
  reload_Engines: () => request("POST", "/api/engines/reload"),
  new_Game: (black, white) => request("POST", "/api/games", { black, white }),
  get_Game: (id) => request("GET", game_Path(id)),
  move: (id, square) => request("POST", `${game_Path(id)}/move`, { square }),
  engine_Move: (id, time_Limit_Ms = 1000) =>
    request("POST", `${game_Path(id)}/engine-move`, { time_limit_ms: time_Limit_Ms }),
  undo: (id) => request("POST", `${game_Path(id)}/undo`),
  set_Players: (id, black, white) => request("POST", `${game_Path(id)}/players`, { black, white }),
};

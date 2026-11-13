// Page logic: starts games, shows whose turn it is and runs the engines' turns.
import { api } from "./api.js";
import { Board, square_Name } from "./board.js";

const HUMAN = "human";
const HUMAN_VS_ENGINE_PAUSE_MS = 450; // long enough to see your own flip land first
const PACE_MS = { relaxed: 1200, normal: 450, quick: 120, step: 0 };

const capital = (word) => word.charAt(0).toUpperCase() + word.slice(1);
const by_Id = (id) => document.getElementById(id);

const el = {
  board: by_Id("board"),
  turn: by_Id("turn"),
  notice: by_Id("notice"),
  error: by_Id("error"),
  announcer: by_Id("announcer"),
  undo: by_Id("undo"),
  retry: by_Id("retry"),
  take_Over: by_Id("take-over"),
  pace_Field: by_Id("pace-field"),
  pace: by_Id("pace"),
  next_Move: by_Id("next-move"),
  form: by_Id("new-game-form"),
  new_Game: by_Id("new-game"),
  black_Player: by_Id("black-player"),
  white_Player: by_Id("white-player"),
  black_About: by_Id("black-player-about"),
  white_About: by_Id("white-player-about"),
  reload_Engines: by_Id("reload-engines"),
  plugin_Errors: by_Id("plugin-errors"),
  plugin_Errors_Summary: by_Id("plugin-errors-summary"),
  plugin_Errors_List: by_Id("plugin-errors-list"),
  mode_Line: by_Id("mode-line"),
  result: by_Id("result"),
  result_Title: by_Id("result-title"),
  result_Detail: by_Id("result-detail"),
  play_Again: by_Id("play-again"),
  players: { black: by_Id("player-black"), white: by_Id("player-white") },
  counts: { black: by_Id("count-black"), white: by_Id("count-white") },
  roles: { black: by_Id("role-black"), white: by_Id("role-white") },
};

const app = {
  view: null,
  engines: [],
  // bumped on every user action; an engine reply from an older generation is dropped
  generation: 0,
  thinking: false,
  busy: 0, // user-started requests still in flight
  engine_Failed: false,
  waiting_For_Step: false,
};

const board = new Board(
  el.board,
  (square) => play_Move(square),
  (square) => {
    const view = app.view;
    if (!view || view.is_over) return;
    const not_Your_Turn = app.busy || app.thinking || !is_Human(view, view.to_move);
    announce(`${square_Name(square)}: ${not_Your_Turn ? "wait for your turn" : "not a legal move"}.`);
  },
);


const is_Human = (view, colour) => view.players[colour] === HUMAN;
const engine_Count = (view) => ["black", "white"].filter((c) => !is_Human(view, c)).length;
const is_Engine_Duel = (view) => engine_Count(view) === 2;

function player_Label(view, colour) {
  if (!is_Human(view, colour)) return view.players[colour];
  return engine_Count(view) === 1 ? "You" : "";
}

function mode_Line(view) {
  if (engine_Count(view) === 0) return "Pass and play";
  if (is_Engine_Duel(view)) return `${view.players.black} vs ${view.players.white}`;
  const you = is_Human(view, "black") ? "black" : "white";
  return `You play ${capital(you)} against ${view.players[you === "black" ? "white" : "black"]}`;
}


function show_Error(message) {
  el.error.textContent = message;
  el.error.hidden = !message;
}

function announce(message) {
  // clear first so screen readers repeat a sentence even if it hasn't changed
  el.announcer.textContent = "";
  requestAnimationFrame(() => {
    el.announcer.textContent = message;
  });
}

function result_Text(view) {
  const { black, white } = view.score;
  if (view.winner === "draw") return { title: "Draw", detail: `${black} all` };
  const winner = capital(view.winner);
  const high = Math.max(black, white);
  const low = Math.min(black, white);
  let title = `${winner} wins`;
  if (engine_Count(view) === 1) {
    title = is_Human(view, view.winner) ? "You win" : `${view.players[view.winner]} wins`;
  }
  return { title, detail: `${winner} ${high} to ${low}` };
}

function turn_Text(view) {
  if (view.is_over) return result_Text(view).title;
  const side = capital(view.to_move);
  if (app.engine_Failed) return `${view.players[view.to_move]} couldn't move`;
  if (!is_Human(view, view.to_move)) {
    return app.waiting_For_Step ? `${side} to play (${view.players[view.to_move]})` : `${side} is thinking…`;
  }
  return engine_Count(view) === 1 ? `Your move (${side})` : `${side} to play`;
}

function pass_Text(view) {
  return view.passed ? `${capital(view.passed)} has no moves — ${capital(view.to_move)} plays again` : "";
}


function render(view, { animate = true, announce_Move = true } = {}) {
  const previous = app.view;
  app.view = view;
  board.render(view, { animate });

  for (const colour of ["black", "white"]) {
    const role = player_Label(view, colour);
    el.counts[colour].textContent = String(view.score[colour]);
    el.players[colour].classList.toggle("active", view.to_move === colour);
    el.players[colour].classList.toggle("thinking", app.thinking && view.to_move === colour);
    el.roles[colour].textContent = role;
    el.roles[colour].title = role;
    el.roles[colour].hidden = !role;
    const to_Move = view.to_move === colour ? ", to move" : "";
    el.players[colour].setAttribute(
      "aria-label",
      `${capital(colour)}${role ? ` (${role})` : ""}: ${view.score[colour]} discs${to_Move}`,
    );
  }

  el.turn.textContent = turn_Text(view);
  const pass = pass_Text(view);
  el.notice.textContent = pass;
  el.notice.hidden = !pass;
  el.mode_Line.textContent = mode_Line(view);

  el.undo.disabled = !view.can_undo || app.thinking || app.busy > 0;
  el.retry.hidden = el.take_Over.hidden = !app.engine_Failed;
  if (app.engine_Failed) el.take_Over.textContent = `Play ${capital(view.to_move)} myself`;
  el.pace_Field.hidden = !is_Engine_Duel(view) || view.is_over;
  el.next_Move.hidden = !app.waiting_For_Step;
  // a new game would race a request in flight (a stale engine reply is dropped anyway)
  el.new_Game.disabled = el.play_Again.disabled = app.busy > 0;
  board.set_Locked(app.thinking || app.busy > 0 || view.is_over || !is_Human(view, view.to_move ?? "black"));

  el.result.hidden = !view.is_over;
  if (view.is_over) {
    const { title, detail } = result_Text(view);
    el.result_Title.textContent = title;
    el.result_Detail.textContent = detail;
  }

  if (announce_Move) announce(move_Announcement(view, previous, pass));

  const just_Ended = view.is_over && !(previous && previous.is_over && previous.id === view.id);
  if (just_Ended) el.play_Again.focus({ preventScroll: true });
}

function move_Announcement(view, previous, pass) {
  const parts = [];
  if (view.last_move !== null && previous && view.move_count > previous.move_count) {
    const mover = view.board[view.last_move] === "B" ? "Black" : "White";
    const flipped = view.last_flips.length;
    parts.push(`${mover} played ${square_Name(view.last_move)}, turning ${flipped} disc${flipped === 1 ? "" : "s"}.`);
  }
  if (pass) parts.push(`${pass}.`);
  if (view.is_over) {
    const { title, detail } = result_Text(view);
    parts.push(`Game over. ${title}, ${detail}.`);
  } else {
    parts.push(`${turn_Text(view)}.`);
  }
  return parts.join(" ");
}

function redraw() {
  if (app.view) render(app.view, { animate: false, announce_Move: false });
}


// runs a request, shows its error if it fails, and keeps the controls locked meanwhile
async function run(action, { lock = true } = {}) {
  show_Error("");
  if (lock) {
    app.busy += 1;
    redraw();
  }
  try {
    return await action();
  } catch (error) {
    show_Error(error.message);
    return null;
  } finally {
    if (lock) {
      app.busy -= 1;
      redraw();
    }
  }
}

async function play_Move(square) {
  const view = app.view;
  if (!view || app.busy > 0 || app.thinking) return;
  const generation = ++app.generation;
  const next = await run(() => api.move(view.id, square));
  if (next && generation === app.generation) {
    render(next);
    take_Engine_Turn();
  }
}

async function start_Game(black, white, { focus_Board = true } = {}) {
  const generation = ++app.generation;
  app.thinking = app.engine_Failed = app.waiting_For_Step = false;
  const view = await run(() => api.new_Game(black, white));
  if (!view || generation !== app.generation) return;
  history.replaceState(null, "", `?game=${encodeURIComponent(view.id)}`);
  app.view = null;
  render(view, { animate: false });
  // keep keyboard players on the board, but not on first load (no focus ring on d3)
  if (focus_Board) board.focus();
  take_Engine_Turn();
}

async function undo() {
  const view = app.view;
  if (!view || el.undo.disabled) return;
  const generation = ++app.generation;
  app.engine_Failed = app.waiting_For_Step = false;
  const next = await run(() => api.undo(view.id));
  if (next && generation === app.generation) {
    render(next, { animate: true, announce_Move: false });
    announce(`Move undone. ${turn_Text(next)}.`);
    if (!next.is_over) board.focus();
  }
}

function engine_Pause_Ms(view) {
  return is_Engine_Duel(view) ? PACE_MS[el.pace.value] : HUMAN_VS_ENGINE_PAUSE_MS;
}

async function take_Engine_Turn({ stepped = false } = {}) {
  const view = app.view;
  if (!view || view.is_over || is_Human(view, view.to_move) || app.thinking) return;
  if (is_Engine_Duel(view) && el.pace.value === "step" && !stepped) {
    app.waiting_For_Step = true;
    redraw();
    return;
  }
  const generation = app.generation;
  app.thinking = true;
  app.engine_Failed = app.waiting_For_Step = false;
  redraw();
  await new Promise((resolve) => setTimeout(resolve, stepped ? 0 : engine_Pause_Ms(view)));
  // if the user started a new game or undid meanwhile, that action now owns the state
  if (generation !== app.generation) return;

  let next = null;
  let failure = null;
  try {
    next = await api.engine_Move(view.id);
  } catch (error) {
    failure = error;
  }
  if (generation !== app.generation) return; // a reply (or error) for a game we've left
  app.thinking = false;
  if (next) {
    show_Error("");
    render(next);
    if (!next.is_over && is_Human(next, next.to_move)) {
      if (el.board.contains(document.activeElement)) board.focus();
      return;
    }
    take_Engine_Turn();
    return;
  }
  app.engine_Failed = true;
  show_Error(failure.message);
  redraw();
  announce(`${turn_Text(view)}: ${failure.message}. Retry, or play this side yourself.`);
}

async function take_Over_Side() {
  const view = app.view;
  if (!view || view.is_over) return;
  const players = { ...view.players, [view.to_move]: HUMAN };
  const generation = ++app.generation;
  const next = await run(() => api.set_Players(view.id, players.black, players.white));
  if (next && generation === app.generation) {
    app.engine_Failed = false;
    render(next, { animate: false, announce_Move: false });
    announce(`You now play ${capital(next.to_move)}. ${turn_Text(next)}.`);
    board.focus();
  }
}


function fill_Player_Menus() {
  for (const select of [el.black_Player, el.white_Player]) {
    const chosen = select.value;
    select.replaceChildren(new Option("Human", HUMAN));
    for (const engine of app.engines) {
      const label = engine.author ? `${engine.name}, by ${engine.author}` : engine.name;
      const option = new Option(label, engine.name);
      option.title = engine.description || engine.name;
      select.append(option);
    }
    // keep the old choice if that engine still exists after a reload
    select.value = [...select.options].some((o) => o.value === chosen) ? chosen : HUMAN;
  }
  describe_Seats();
}

// the quiet line under each menu: what the chosen engine says about itself
function describe_Seats() {
  for (const [select, about] of [[el.black_Player, el.black_About], [el.white_Player, el.white_About]]) {
    const engine = app.engines.find((e) => e.name === select.value);
    about.textContent = engine ? engine.description : "";
    about.title = about.textContent;
  }
}

function show_Plugin_Errors(errors) {
  el.plugin_Errors.hidden = errors.length === 0;
  el.plugin_Errors_Summary.textContent =
    errors.length === 1 ? "1 plugin failed to load" : `${errors.length} plugins failed to load`;
  el.plugin_Errors_List.replaceChildren(
    ...errors.map((error) => {
      const item = document.createElement("li");
      const file = document.createElement("strong");
      file.textContent = error.file;
      item.append(file, `: ${error.message}`);
      return item;
    }),
  );
}

async function load_Engines() {
  try {
    const [engines, errors] = await Promise.all([api.engines(), api.engine_Errors()]);
    app.engines = engines;
    show_Plugin_Errors(errors);
  } catch (error) {
    show_Error(error.message);
  }
  fill_Player_Menus();
}

async function reload_Engines() {
  const result = await run(() => api.reload_Engines());
  if (!result) return;
  app.engines = result.engines;
  fill_Player_Menus();
  show_Plugin_Errors(result.errors);
  const count = result.engines.length;
  announce(`Engines reloaded: ${count} available${result.errors.length ? `, ${result.errors.length} failed` : ""}.`);
}

function select_Players(view) {
  // the menus mirror the game on screen, so "Start new game" repeats the same match-up
  for (const [colour, select] of [["black", el.black_Player], ["white", el.white_Player]]) {
    const name = view.players[colour];
    if (![...select.options].some((o) => o.value === name)) select.append(new Option(name, name));
    select.value = name;
  }
  describe_Seats();
}


el.undo.addEventListener("click", undo);
el.retry.addEventListener("click", () => {
  app.engine_Failed = false;
  take_Engine_Turn({ stepped: true });
});
el.take_Over.addEventListener("click", take_Over_Side);
el.next_Move.addEventListener("click", () => {
  app.waiting_For_Step = false;
  take_Engine_Turn({ stepped: true });
});
el.pace.addEventListener("change", () => {
  if (el.pace.value !== "step" && app.waiting_For_Step) {
    app.waiting_For_Step = false;
    take_Engine_Turn();
  }
});
el.reload_Engines.addEventListener("click", reload_Engines);
el.black_Player.addEventListener("change", describe_Seats);
el.white_Player.addEventListener("change", describe_Seats);
el.form.addEventListener("submit", (event) => {
  event.preventDefault();
  start_Game(el.black_Player.value, el.white_Player.value);
});
el.play_Again.addEventListener("click", () => {
  const view = app.view;
  start_Game(view ? view.players.black : HUMAN, view ? view.players.white : HUMAN);
});
document.addEventListener("keydown", (event) => {
  if (event.key.toLowerCase() !== "u" || event.ctrlKey || event.metaKey || event.altKey) return;
  if (event.target.closest("select, input, textarea, summary")) return;
  undo();
});

async function start_Up() {
  await load_Engines();
  const id = new URLSearchParams(location.search).get("game");
  if (id) {
    const view = await run(() => api.get_Game(id));
    if (view) {
      select_Players(view);
      render(view, { animate: false });
      take_Engine_Turn();
      return;
    }
    show_Error("That game is gone (the server was restarted), so here's a fresh one.");
  }
  const message = el.error.textContent;
  await start_Game(HUMAN, HUMAN, { focus_Board: false });
  if (message) show_Error(message);
}

start_Up();

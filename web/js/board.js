// The 8x8 board: drawing, flipping discs, clicks and key presses. Square 0 is a1, 63 is h8.

const COLUMNS = "abcdefgh";
const COLOUR_OF = { B: "black", W: "white", ".": "empty" };
const RIPPLE_FALLBACK_MS = 55; // matches --ripple-ms in the CSS

export const square_Name = (square) => `${COLUMNS[square % 8]}${Math.floor(square / 8) + 1}`;

const row_Of = (square) => Math.floor(square / 8);
const column_Of = (square) => square % 8;

// king-move distance between two squares; discs further from the new one flip later
const distance = (a, b) => Math.max(Math.abs(row_Of(a) - row_Of(b)), Math.abs(column_Of(a) - column_Of(b)));

export class Board {
  /** root is the role="grid" element; on_Play gets legal squares, on_Rejected any other */
  constructor(root, on_Play, on_Rejected = () => {}) {
    this.root = root;
    this.on_Play = on_Play;
    this.on_Rejected = on_Rejected;
    this.cells = [];
    this.buttons = [];
    this.focus_Index = 0; // the one square that's in the Tab order ("roving tabindex")
    this.locked = false;
    this.legal = new Set();
    this.shown_Board = null;
    this.#build();
  }

  #build() {
    const rows = document.createDocumentFragment();
    for (let row = 0; row < 8; row++) {
      const row_Element = document.createElement("div");
      row_Element.className = "row";
      row_Element.setAttribute("role", "row");
      for (let column = 0; column < 8; column++) {
        row_Element.append(this.#make_Cell(row * 8 + column));
      }
      rows.append(row_Element);
    }
    this.root.append(rows);

    this.root.addEventListener("click", (event) => {
      const button = event.target.closest("button.sq");
      if (button) this.#choose(Number(button.dataset.square));
    });
    this.root.addEventListener("keydown", (event) => this.#on_Key(event));
    this.root.addEventListener("focusin", (event) => {
      const button = event.target.closest("button.sq");
      if (button) this.#move_Focus_To(Number(button.dataset.square), { focus: false });
    });
  }

  // A cell holds a transparent button (for clicks, keys and focus) and the disc under it.
  #make_Cell(square) {
    const cell = document.createElement("div");
    cell.className = "cell";
    cell.setAttribute("role", "gridcell");
    cell.dataset.color = "empty";
    cell.dataset.square = String(square);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "sq";
    button.tabIndex = square === 0 ? 0 : -1;
    button.dataset.square = String(square);

    const disc = document.createElement("span");
    disc.className = "disc";
    disc.setAttribute("aria-hidden", "true");
    disc.innerHTML = '<span class="face face-black"></span><span class="face face-white"></span>';

    cell.append(button, disc);
    this.cells.push(cell);
    this.buttons.push(button);
    return cell;
  }

  #choose(square) {
    this.#move_Focus_To(square, { focus: false });
    if (this.locked || !this.legal.has(square)) {
      this.on_Rejected(square);
      return;
    }
    this.on_Play(square);
  }

  #on_Key(event) {
    const button = event.target.closest("button.sq");
    if (!button) return;
    const square = Number(button.dataset.square);
    const row = row_Of(square);
    const column = column_Of(square);
    const target = {
      ArrowUp: row > 0 ? square - 8 : square,
      ArrowDown: row < 7 ? square + 8 : square,
      ArrowLeft: column > 0 ? square - 1 : square,
      ArrowRight: column < 7 ? square + 1 : square,
      Home: event.ctrlKey ? 0 : row * 8,
      End: event.ctrlKey ? 63 : row * 8 + 7,
    }[event.key];

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault(); // Space would otherwise scroll the page
      this.#choose(square);
    } else if (target !== undefined) {
      event.preventDefault();
      this.#move_Focus_To(target, { focus: true });
    }
  }

  #move_Focus_To(square, { focus }) {
    if (square !== this.focus_Index) {
      this.buttons[this.focus_Index].tabIndex = -1;
      this.buttons[square].tabIndex = 0;
      this.focus_Index = square;
    }
    if (focus) this.buttons[square].focus();
  }

  /** Focus the current square if it's playable, otherwise the first legal move. */
  focus() {
    if (!this.legal.has(this.focus_Index) && this.legal.size) {
      this.#move_Focus_To(Math.min(...this.legal), { focus: false });
    }
    this.buttons[this.focus_Index].focus();
  }

  set_Locked(locked) {
    this.locked = locked;
    this.root.classList.toggle("locked", locked);
    // aria-disabled, not aria-busy: busy can make screen readers stop reading the board
    for (const button of this.buttons) button.setAttribute("aria-disabled", String(locked));
  }

  /** Draw a game view; with `animate` the new disc settles and the flips ripple outward. */
  render(view, { animate = true } = {}) {
    const before = this.shown_Board;
    this.shown_Board = view.board;
    this.legal = new Set(view.legal_moves);
    this.root.dataset.turn = view.to_move ?? "none";
    const placed = view.last_move;
    const flipped = new Set(view.last_flips);
    const ripple_Ms = Number.parseInt(getComputedStyle(this.root).getPropertyValue("--ripple-ms"), 10);

    for (let square = 0; square < 64; square++) {
      const cell = this.cells[square];
      const now = view.board[square];
      const changed = before !== null && before[square] !== now;

      const delay = animate && changed && placed !== null && flipped.has(square)
        ? distance(square, placed) * (ripple_Ms || RIPPLE_FALLBACK_MS)
        : 0;
      cell.style.setProperty("--delay", `${delay}ms`);

      // only a disc that already existed flips; a new one would spin in from its black face
      const turns_Over = animate && changed && before[square] !== ".";
      cell.querySelector(".disc").style.transition = turns_Over ? "" : "none";

      cell.dataset.color = COLOUR_OF[now];
      cell.classList.toggle("legal", this.legal.has(square));
      cell.classList.toggle("last", square === placed);
      cell.classList.remove("placed");
      if (animate && changed && before[square] === "." && square === placed) {
        void cell.offsetWidth; // forces a reflow so the settle animation starts again
        cell.classList.add("placed");
      }
      this.buttons[square].setAttribute("aria-label", this.#label(square, now, view));
    }
  }

  #label(square, now, view) {
    const parts = [square_Name(square), COLOUR_OF[now]];
    if (this.legal.has(square)) parts.push("legal move");
    if (square === view.last_move) parts.push("last move");
    return parts.join(", ");
  }
}

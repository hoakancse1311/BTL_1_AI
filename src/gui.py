"""
gui.py - Tkinter GUI for Minesweeper with Rule-based and BFS/DFS AI search.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from ai_solver import MinesweeperAI, Move
from game_logic import MinesweeperGame


class MinesweeperGUI:
    """GUI for Minesweeper with step-by-step AI explanations."""

    COLOR_MAP = {
        1: "#1976D2",
        2: "#388E3C",
        3: "#D32F2F",
        4: "#512DA8",
        5: "#C2185B",
        6: "#0097A7",
        7: "#212121",
        8: "#616161",
    }

    BG_UNREVEALED = "#E0E0E0"
    BG_REVEALED = "#FFFFFF"
    BG_MINE_EXPLODED = "#FFCDD2"
    BG_HINT = "#C8E6C9"

    # Fixed, reproducible large board for demonstrating the transition
    # from classic Rules to BFS/DFS search.
    CHALLENGE_ROWS = 25
    CHALLENGE_COLS = 30
    CHALLENGE_MINES = 150
    CHALLENGE_SEED = 4

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("HCMUT - Minesweeper AI (CO3061) | BTL 1")

        # Root layout: keep header/controls/status visible at all times and let
        # only the board area consume the remaining space. This prevents large
        # boards (especially 25x30) from pushing the lower rows off-screen.
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)
        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=1)
        self.root.rowconfigure(3, weight=0)

        # Game configuration
        self.current_rows = 9
        self.current_cols = 9
        self.current_mines = 10
        self.current_seed = None

        # AI configuration
        self.ai_mode_var = tk.StringVar(value=MinesweeperAI.RULES_ONLY)
        self.search_algo_var = tk.StringVar(value="BFS")

        self.game = MinesweeperGame(
            self.current_rows,
            self.current_cols,
            self.current_mines,
            flood_algorithm=self.search_algo_var.get(),
            random_seed=self.current_seed,
        )
        self.ai = MinesweeperAI(self.game)

        # Autoplay state
        self.is_auto_playing = False
        self.auto_play_delay_ms = 180
        self.hint_cells = []
        self.ai_step_count = 0

        # Window / responsive layout state
        self.is_fullscreen = False
        self._resize_after_id = None

        self._setup_styles()
        self._build_menu()
        self._build_header()
        self._build_control_panel()
        self._build_board()
        self._build_status_bar()

        # Start at a sensible size, but keep the window resizable.
        # The board expands with the window, and long AI explanations remain
        # inside the fixed-height status area.
        self._fit_initial_window()

        # Responsive board + display shortcuts.
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.bind("<F11>", self.toggle_fullscreen, add="+")
        self.root.bind("<Escape>", self.exit_fullscreen, add="+")
        self.root.bind("<Control-m>", self.toggle_maximize, add="+")

        self._update_timer()

    # ------------------------------------------------------------------
    # Window sizing / fullscreen / responsive board
    # ------------------------------------------------------------------
    def _unlock_window_size(self):
        """Keep the top-level window freely resizable."""
        self.root.resizable(True, True)
        self.root.minsize(480, 420)

    def _fit_initial_window(self):
        """Choose a comfortable initial size without locking the window."""
        self.root.update_idletasks()

        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        width = min(max(req_w, 620), max(620, screen_w - 100))
        height = min(max(req_h, 560), max(560, screen_h - 140))

        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(480, 420)
        self.root.resizable(True, True)

    def _ensure_board_fits_when_normal(self):
        """
        Enlarge a normal window only when a newly selected board needs more room.

        The function never shrinks the current window. Maximized/fullscreen windows
        are left untouched, so changing difficulty does not kick the user out of
        the chosen display mode.
        """
        if self.is_fullscreen:
            return

        try:
            if self.root.state() == "zoomed":
                return
        except tk.TclError:
            pass

        self.root.update_idletasks()
        req_w = self.root.winfo_reqwidth()
        req_h = self.root.winfo_reqheight()
        cur_w = self.root.winfo_width()
        cur_h = self.root.winfo_height()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        target_w = min(max(cur_w, req_w), max(480, screen_w - 60))
        target_h = min(max(cur_h, req_h), max(420, screen_h - 100))

        if target_w != cur_w or target_h != cur_h:
            x = max(0, (screen_w - target_w) // 2)
            y = max(0, (screen_h - target_h) // 3)
            self.root.geometry(f"{target_w}x{target_h}+{x}+{y}")

    def _maximize_large_board_if_needed(self):
        """Give 25x30-class boards the largest practical viewport automatically."""
        if not (self.current_rows >= 20 or self.current_cols >= 20):
            return
        if self.is_fullscreen:
            self._sync_board_viewport()
            return

        try:
            if self.root.state() != "zoomed":
                self.root.state("zoomed")
        except tk.TclError:
            # Cross-platform fallback: use almost all usable screen area.
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            self.root.geometry(f"{max(700, screen_w - 20)}x{max(560, screen_h - 80)}+0+0")

        self.root.after_idle(self._sync_board_viewport)

    def toggle_maximize(self, _event=None):
        """Toggle the normal Windows maximize state (Ctrl+M)."""
        if self.is_fullscreen:
            self.exit_fullscreen()

        try:
            if self.root.state() == "zoomed":
                self.root.state("normal")
            else:
                self.root.state("zoomed")
        except tk.TclError:
            # Fallback for platforms that expose maximization as an attribute.
            try:
                current = bool(self.root.attributes("-zoomed"))
                self.root.attributes("-zoomed", not current)
            except tk.TclError:
                pass
        return "break"

    def toggle_fullscreen(self, _event=None):
        """Toggle borderless fullscreen mode (F11)."""
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)
        if hasattr(self, "fullscreen_var"):
            self.fullscreen_var.set(self.is_fullscreen)
        return "break"

    def exit_fullscreen(self, _event=None):
        """Leave fullscreen mode with Escape."""
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.root.attributes("-fullscreen", False)
            if hasattr(self, "fullscreen_var"):
                self.fullscreen_var.set(False)
        return "break"

    def _on_root_configure(self, event):
        """Debounce resize events before updating board font/borders."""
        if event.widget is not self.root:
            return

        if self._resize_after_id is not None:
            try:
                self.root.after_cancel(self._resize_after_id)
            except tk.TclError:
                pass

        self._resize_after_id = self.root.after(60, self._apply_responsive_board_style)

    def _apply_responsive_board_style(self):
        """Scale the cell text and borders according to the visible board area."""
        self._resize_after_id = None
        if not hasattr(self, "board_frame") or not hasattr(self, "buttons"):
            return
        if not self.buttons or not self.buttons[0]:
            return

        if hasattr(self, "board_canvas"):
            board_w = max(1, self.board_canvas.winfo_width() - 10)
            board_h = max(1, self.board_canvas.winfo_height() - 10)
        else:
            board_w = max(1, self.board_frame.winfo_width() - 10)
            board_h = max(1, self.board_frame.winfo_height() - 10)
        cell_w = board_w / max(1, self.current_cols)
        cell_h = board_h / max(1, self.current_rows)
        cell_px = max(8.0, min(cell_w, cell_h))

        # Large boards must stay vertically compact. Tk buttons have a minimum
        # requested height based on their font, so an aggressive large-board
        # font scale is needed to keep all 25 rows visible on common 720p/768p
        # laptop screens. Smaller boards can grow much more freely.
        large_board = self.current_rows >= 20 or self.current_cols >= 20
        if large_board:
            font_size = max(5, min(12, int(cell_px * 0.30)))
            border = 1
        else:
            font_size = max(8, min(26, int(cell_px * 0.40)))
            border = 1 if cell_px < 30 else 2

        for row in self.buttons:
            for btn in row:
                btn.config(font=("Segoe UI", font_size, "bold"), bd=border)

        if hasattr(self, "board_canvas"):
            self.board_canvas.configure(scrollregion=self.board_canvas.bbox("all"))

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure(
            "Counter.TLabel",
            font=("Consolas", 14, "bold"),
            foreground="#D32F2F",
        )
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"))

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        game_menu = tk.Menu(menubar, tearoff=0)
        game_menu.add_command(
            label="5x5 Mini (3 Mìn)",
            command=lambda: self.change_difficulty(5, 5, 3),
        )
        game_menu.add_command(
            label="9x9 Chuẩn (10 Mìn)",
            command=lambda: self.change_difficulty(9, 9, 10),
        )
        game_menu.add_command(
            label="16x16 Trung cấp (40 Mìn)",
            command=lambda: self.change_difficulty(16, 16, 40),
        )
        game_menu.add_command(
            label="25x30 Search Challenge (150 Mìn)",
            command=self.load_search_challenge,
        )
        game_menu.add_separator()
        game_menu.add_command(label="Tùy chỉnh kích thước...", command=self._open_custom_dialog)
        game_menu.add_separator()
        game_menu.add_command(label="Ván mới (F2)", command=self.restart_game)
        game_menu.add_command(label="Thoát", command=self.root.quit)
        menubar.add_cascade(label="Trò chơi", menu=game_menu)

        ai_menu = tk.Menu(menubar, tearoff=0)
        ai_menu.add_radiobutton(
            label="Rule-based only",
            variable=self.ai_mode_var,
            value=MinesweeperAI.RULES_ONLY,
            command=self._on_ai_mode_change,
        )
        ai_menu.add_radiobutton(
            label="Hybrid: Rules -> BFS/DFS Search",
            variable=self.ai_mode_var,
            value=MinesweeperAI.HYBRID,
            command=self._on_ai_mode_change,
        )
        ai_menu.add_separator()
        ai_menu.add_radiobutton(
            label="BFS Search",
            variable=self.search_algo_var,
            value="BFS",
            command=self._on_algo_change,
        )
        ai_menu.add_radiobutton(
            label="DFS Search",
            variable=self.search_algo_var,
            value="DFS",
            command=self._on_algo_change,
        )
        menubar.add_cascade(label="AI / Thuật toán", menu=ai_menu)

        # Display controls: normal resize, maximize, and true fullscreen.
        self.fullscreen_var = tk.BooleanVar(value=False)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(
            label="Phóng to / Khôi phục cửa sổ (Ctrl+M)",
            command=self.toggle_maximize,
        )
        view_menu.add_checkbutton(
            label="Toàn màn hình (F11)",
            variable=self.fullscreen_var,
            command=self.toggle_fullscreen,
        )
        view_menu.add_command(
            label="Thoát toàn màn hình (Esc)",
            command=self.exit_fullscreen,
        )
        menubar.add_cascade(label="Hiển thị", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Thông tin nhóm BTL", command=self._show_about)
        menubar.add_cascade(label="Trợ giúp", menu=help_menu)

        self.root.bind("<F2>", lambda _event: self.restart_game())

    def _build_header(self):
        header_frame = tk.Frame(self.root, bg="#263238", pady=6, padx=10)
        header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_mines = tk.Label(
            header_frame,
            text=f"Mines {self.game.get_remaining_mines():03d}",
            font=("Consolas", 14, "bold"),
            fg="#FF5252",
            bg="#1E1E1E",
            width=10,
            relief=tk.SUNKEN,
            bd=2,
        )
        self.lbl_mines.pack(side=tk.LEFT, padx=5)

        self.btn_smiley = tk.Button(
            header_frame,
            text="😊",
            font=("Segoe UI Emoji", 14),
            width=3,
            command=self.restart_game,
            relief=tk.RAISED,
            bd=2,
            bg="#ECEFF1",
            cursor="hand2",
        )
        self.btn_smiley.pack(side=tk.LEFT, expand=True)

        self.lbl_timer = tk.Label(
            header_frame,
            text="Time 000",
            font=("Consolas", 14, "bold"),
            fg="#69F0AE",
            bg="#1E1E1E",
            width=10,
            relief=tk.SUNKEN,
            bd=2,
        )
        self.lbl_timer.pack(side=tk.RIGHT, padx=5)

    def _build_control_panel(self):
        ctrl_frame = tk.Frame(self.root, bg="#ECEFF1", pady=5, padx=8)
        ctrl_frame.grid(row=1, column=0, sticky="ew")

        preset_frame = tk.Frame(ctrl_frame, bg="#ECEFF1")
        preset_frame.pack(side=tk.TOP, fill=tk.X, pady=2)

        tk.Button(
            preset_frame,
            text="5x5",
            font=("Segoe UI", 8),
            bg="#CFD8DC",
            command=lambda: self.change_difficulty(5, 5, 3),
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            preset_frame,
            text="9x9",
            font=("Segoe UI", 8),
            bg="#CFD8DC",
            command=lambda: self.change_difficulty(9, 9, 10),
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            preset_frame,
            text="16x16",
            font=("Segoe UI", 8),
            bg="#CFD8DC",
            command=lambda: self.change_difficulty(16, 16, 40),
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            preset_frame,
            text="25x30 Search Challenge",
            font=("Segoe UI", 8, "bold"),
            bg="#FFE0B2",
            command=self.load_search_challenge,
        ).pack(side=tk.LEFT, padx=5)

        mode_frame = tk.Frame(ctrl_frame, bg="#ECEFF1")
        mode_frame.pack(side=tk.TOP, fill=tk.X, pady=2)

        tk.Label(
            mode_frame,
            text="AI:",
            font=("Segoe UI", 8, "bold"),
            bg="#ECEFF1",
        ).pack(side=tk.LEFT, padx=(2, 0))
        tk.Radiobutton(
            mode_frame,
            text="Rule-based",
            variable=self.ai_mode_var,
            value=MinesweeperAI.RULES_ONLY,
            command=self._on_ai_mode_change,
            bg="#ECEFF1",
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            mode_frame,
            text="Hybrid Rule -> Search",
            variable=self.ai_mode_var,
            value=MinesweeperAI.HYBRID,
            command=self._on_ai_mode_change,
            bg="#ECEFF1",
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT)

        tk.Label(
            mode_frame,
            text=" | Search:",
            font=("Segoe UI", 8, "bold"),
            bg="#ECEFF1",
        ).pack(side=tk.LEFT, padx=(6, 0))
        tk.Radiobutton(
            mode_frame,
            text="BFS",
            variable=self.search_algo_var,
            value="BFS",
            command=self._on_algo_change,
            bg="#ECEFF1",
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            mode_frame,
            text="DFS",
            variable=self.search_algo_var,
            value="DFS",
            command=self._on_algo_change,
            bg="#ECEFF1",
            font=("Segoe UI", 8),
        ).pack(side=tk.LEFT)

        ai_frame = tk.Frame(ctrl_frame, bg="#ECEFF1")
        ai_frame.pack(side=tk.TOP, fill=tk.X, pady=3)

        self.btn_hint = tk.Button(
            ai_frame,
            text="Gợi ý AI",
            bg="#E8F5E9",
            fg="#2E7D32",
            font=("Segoe UI", 8, "bold"),
            command=self.give_ai_hint,
            cursor="hand2",
        )
        self.btn_hint.pack(side=tk.LEFT, padx=3)

        self.btn_step = tk.Button(
            ai_frame,
            text="AI đi 1 bước",
            bg="#E1F5FE",
            fg="#0277BD",
            font=("Segoe UI", 8, "bold"),
            command=self.step_ai,
            cursor="hand2",
        )
        self.btn_step.pack(side=tk.LEFT, padx=3)

        self.btn_autoplay = tk.Button(
            ai_frame,
            text="AI tự giải",
            bg="#EDE7F6",
            fg="#512DA8",
            font=("Segoe UI", 8, "bold"),
            command=self.toggle_autoplay,
            cursor="hand2",
        )
        self.btn_autoplay.pack(side=tk.LEFT, padx=3)

        self.btn_fullscreen = tk.Button(
            ai_frame,
            text="Toàn màn hình (F11)",
            bg="#FFF3E0",
            fg="#E65100",
            font=("Segoe UI", 8, "bold"),
            command=self.toggle_fullscreen,
            cursor="hand2",
        )
        self.btn_fullscreen.pack(side=tk.RIGHT, padx=3)

        self.btn_maximize = tk.Button(
            ai_frame,
            text="Phóng to",
            bg="#F3E5F5",
            fg="#6A1B9A",
            font=("Segoe UI", 8, "bold"),
            command=self.toggle_maximize,
            cursor="hand2",
        )
        self.btn_maximize.pack(side=tk.RIGHT, padx=3)

    def _build_board(self):
        """Build a scroll-safe responsive board viewport.

        The old layout packed the 25x30 button grid directly into the root.
        Its requested height could be larger than the usable screen height, so
        the last rows were clipped. The board now lives inside a Canvas viewport:

        - if the window is large enough, the board stretches to fill the area;
        - if the screen is too small or Windows DPI is high, scrollbars provide
          access to every row/column instead of hiding them.
        """
        if hasattr(self, "board_container"):
            self.board_container.destroy()
        elif hasattr(self, "board_frame"):
            self.board_frame.destroy()

        large_board = self.current_rows >= 20 or self.current_cols >= 20

        self.board_container = tk.Frame(self.root, bg="#B0BEC5", bd=0)
        self.board_container.grid(row=2, column=0, sticky="nsew")
        self.board_container.rowconfigure(0, weight=1)
        self.board_container.columnconfigure(0, weight=1)

        self.board_canvas = tk.Canvas(
            self.board_container,
            bg="#B0BEC5",
            highlightthickness=0,
            bd=0,
        )
        self.board_canvas.grid(row=0, column=0, sticky="nsew")

        self.board_vscroll = ttk.Scrollbar(
            self.board_container, orient=tk.VERTICAL, command=self.board_canvas.yview
        )
        self.board_hscroll = ttk.Scrollbar(
            self.board_container, orient=tk.HORIZONTAL, command=self.board_canvas.xview
        )
        self.board_canvas.configure(
            yscrollcommand=self.board_vscroll.set,
            xscrollcommand=self.board_hscroll.set,
        )
        self.board_vscroll.grid(row=0, column=1, sticky="ns")
        self.board_hscroll.grid(row=1, column=0, sticky="ew")

        pad = 2 if large_board else 5
        self.board_frame = tk.Frame(
            self.board_canvas,
            bg="#B0BEC5",
            padx=pad,
            pady=pad,
            bd=3,
            relief=tk.SUNKEN,
        )
        self._board_window_id = self.board_canvas.create_window(
            (0, 0), window=self.board_frame, anchor="nw"
        )

        # Every row/column receives an equal share of available board space.
        for r in range(self.current_rows):
            self.board_frame.rowconfigure(r, weight=1, uniform="board_row")
        for c in range(self.current_cols):
            self.board_frame.columnconfigure(c, weight=1, uniform="board_col")

        self.buttons = []
        font_size = 6 if large_board else (9 if self.current_cols > 9 else 10)
        border = 1 if large_board else 2
        grid_pad = 0 if large_board else 1
        button_width = 1 if large_board else 2

        for r in range(self.current_rows):
            row_buttons = []
            for c in range(self.current_cols):
                btn = tk.Button(
                    self.board_frame,
                    text="",
                    width=button_width,
                    height=1,
                    font=("Segoe UI", font_size, "bold"),
                    bg=self.BG_UNREVEALED,
                    relief=tk.RAISED,
                    bd=border,
                    padx=0,
                    pady=0,
                    cursor="hand2",
                )
                btn.grid(
                    row=r,
                    column=c,
                    padx=grid_pad,
                    pady=grid_pad,
                    sticky="nsew",
                )
                btn.bind(
                    "<Button-1>",
                    lambda _event, row=r, col=c: self._on_left_click(row, col),
                )
                btn.bind(
                    "<Button-3>",
                    lambda _event, row=r, col=c: self._on_right_click(row, col),
                )
                row_buttons.append(btn)
            self.buttons.append(row_buttons)

        # Resize the inner board to the viewport when there is enough room.
        # Otherwise keep its natural minimum size and enable scrolling.
        self.board_canvas.bind("<Configure>", self._on_board_canvas_configure, add="+")
        self.board_frame.bind("<Configure>", self._refresh_board_scrollregion, add="+")
        self.root.after_idle(self._sync_board_viewport)

    def _on_board_canvas_configure(self, _event=None):
        self._sync_board_viewport()

    def _refresh_board_scrollregion(self, _event=None):
        if hasattr(self, "board_canvas"):
            self.board_canvas.configure(scrollregion=self.board_canvas.bbox("all"))

    def _sync_board_viewport(self):
        """Fit the board to the visible area, with scrollbars as a fallback."""
        if not hasattr(self, "board_canvas") or not hasattr(self, "board_frame"):
            return
        if not self.board_canvas.winfo_exists() or not self.board_frame.winfo_exists():
            return

        # Apply the compact/responsive font first because a Tk Button's font
        # directly affects its requested height. Then measure the true minimum
        # board size and decide whether scrolling is actually necessary.
        self._apply_responsive_board_style()
        self.board_frame.update_idletasks()
        view_w = max(1, self.board_canvas.winfo_width())
        view_h = max(1, self.board_canvas.winfo_height())
        req_w = max(1, self.board_frame.winfo_reqwidth())
        req_h = max(1, self.board_frame.winfo_reqheight())

        target_w = max(view_w, req_w)
        target_h = max(view_h, req_h)
        self.board_canvas.itemconfigure(
            self._board_window_id, width=target_w, height=target_h
        )
        self.board_canvas.configure(scrollregion=(0, 0, target_w, target_h))

    def _build_status_bar(self):
        """
        Fixed-height Text widget.

        Unlike a Label whose requested width follows its content, this widget
        wraps long explanations inside the current window without forcing a resize.
        """
        self.status_bar = tk.Text(
            self.root,
            height=3,
            width=1,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            bd=1,
            relief=tk.SUNKEN,
            padx=6,
            pady=4,
            bg="#ECEFF1",
            cursor="arrow",
            takefocus=0,
        )
        self.status_bar.grid(row=3, column=0, sticky="ew")
        self.status_bar.config(state=tk.DISABLED)
        self.set_status(
            "Sẵn sàng. AI mặc định dùng Rule-based; khi Rule-based bị kẹt, "
            "chuyển sang Hybrid để dùng BFS/DFS Search."
        )

    # ------------------------------------------------------------------
    # Controls and status
    # ------------------------------------------------------------------
    def _on_ai_mode_change(self):
        mode = self.ai_mode_var.get()
        if mode == MinesweeperAI.RULES_ONLY:
            self.set_status(
                "AI = Rule-based only: chỉ dùng 2 luật Minesweeper chắc chắn. "
                "Nếu không suy ra được ô an toàn/mìn, AI sẽ dừng."
            )
        else:
            self.set_status(
                f"AI = Hybrid: dùng Rule-based trước; khi kẹt mới chuyển sang "
                f"{self.search_algo_var.get()} Search."
            )

    def _on_algo_change(self):
        algorithm = self.search_algo_var.get()
        self.game.flood_algorithm = algorithm
        self.set_status(
            f"Đã chọn {algorithm}. Trong Hybrid, {algorithm} dùng để duyệt không gian "
            "trạng thái khi Rule-based bị kẹt; game cũng dùng cùng thuật toán cho loang ô 0."
        )

    def set_status(self, text: str):
        """Update explanation text without changing application dimensions."""
        self.status_bar.config(state=tk.NORMAL)
        self.status_bar.delete("1.0", tk.END)
        self.status_bar.insert("1.0", text)
        self.status_bar.config(state=tk.DISABLED)

    def _action_text(self, move: Move) -> str:
        if move.action == Move.FLAG:
            return "CẮM CỜ"
        if move.action == Move.GUESS:
            return "MỞ Ô (có rủi ro)"
        return "MỞ Ô"

    # ------------------------------------------------------------------
    # Human actions
    # ------------------------------------------------------------------
    def _on_left_click(self, r: int, c: int):
        if self.is_auto_playing:
            self.toggle_autoplay()

        self._clear_hints()
        success = self.game.reveal_cell(r, c)
        self._update_board_display()

        if not success:
            self.btn_smiley.config(text="😵")
            self.set_status(f"Bạn đã chạm mìn tại ô ({r}, {c}). Trò chơi kết thúc.")
        elif self.game.won:
            self.btn_smiley.config(text="😎")
            self.set_status(
                f"CHIẾN THẮNG. Hoàn thành bàn cờ trong "
                f"{self.game.get_elapsed_time()} giây."
            )
        else:
            revealed_count = len(self.game.last_flood_revealed)
            if revealed_count > 1:
                self.set_status(
                    f"[{self.game.last_algorithm_used} Flood Fill] "
                    f"Đã loang mở {revealed_count} ô từ ô ({r}, {c})."
                )
            else:
                self.set_status(f"Đã mở ô ({r}, {c}).")

    def _on_right_click(self, r: int, c: int):
        if self.is_auto_playing:
            return

        self._clear_hints()
        self.game.toggle_flag(r, c)
        self._update_board_display()
        self.set_status(
            f"Đã đổi trạng thái cờ tại ô ({r}, {c}). "
            f"Số mìn còn lại: {self.game.get_remaining_mines()}."
        )

    # ------------------------------------------------------------------
    # Board rendering
    # ------------------------------------------------------------------
    def _update_board_display(self):
        self.lbl_mines.config(
            text=f"Mines {max(0, self.game.get_remaining_mines()):03d}"
        )

        for r in range(self.current_rows):
            for c in range(self.current_cols):
                btn = self.buttons[r][c]
                cell = self.game.board[r][c]

                if cell.is_revealed:
                    btn.config(relief=tk.SUNKEN, bd=1)
                    if cell.is_mine:
                        btn.config(
                            text="*",
                            bg=self.BG_MINE_EXPLODED,
                            fg="#B71C1C",
                        )
                    elif cell.neighbor_mines > 0:
                        btn.config(
                            text=str(cell.neighbor_mines),
                            bg=self.BG_REVEALED,
                            fg=self.COLOR_MAP.get(cell.neighbor_mines, "#000000"),
                        )
                    else:
                        btn.config(text="", bg=self.BG_REVEALED)
                elif cell.is_flagged:
                    btn.config(
                        text="F",
                        bg=self.BG_UNREVEALED,
                        fg="#D32F2F",
                        relief=tk.RAISED,
                    )
                elif (r, c) not in self.hint_cells:
                    btn.config(text="", bg=self.BG_UNREVEALED, relief=tk.RAISED)

    def _clear_hints(self):
        for r, c in self.hint_cells:
            if (
                not self.game.board[r][c].is_revealed
                and not self.game.board[r][c].is_flagged
            ):
                self.buttons[r][c].config(bg=self.BG_UNREVEALED)
        self.hint_cells.clear()

    # ------------------------------------------------------------------
    # AI actions
    # ------------------------------------------------------------------
    def _get_ai_move(self):
        return self.ai.get_next_move(
            strategy=self.ai_mode_var.get(),
            search_algorithm=self.search_algo_var.get(),
        )

    def give_ai_hint(self):
        if self.game.game_over:
            return

        self._clear_hints()
        self.btn_smiley.config(text="🤔")
        move = self._get_ai_move()
        self.btn_smiley.config(text="😊")

        if not move:
            if self.ai_mode_var.get() == MinesweeperAI.RULES_ONLY:
                self.set_status(
                    "[RULE-BASED DỪNG] Hai luật cơ bản không còn suy ra được nước đi "
                    "chắc chắn. Hãy chọn Hybrid để tiếp tục bằng BFS/DFS Search."
                )
            else:
                self.set_status("Không còn nước đi AI khả dụng.")
            return

        self.hint_cells.append((move.row, move.col))
        self.buttons[move.row][move.col].config(bg=self.BG_HINT)

        self.set_status(
            f"[GỢI Ý][{move.method}] {self._action_text(move)} "
            f"({move.row}, {move.col}) | P(mìn)={move.probability:.1%}. {move.reason}"
        )

    def step_ai(self):
        """Execute one AI step. Returns True if a move was executed."""
        if self.game.game_over:
            return False

        self._clear_hints()
        self.btn_smiley.config(text="🤔")
        move = self._get_ai_move()
        self.btn_smiley.config(text="😊")

        if not move:
            if self.ai_mode_var.get() == MinesweeperAI.RULES_ONLY:
                self.set_status(
                    f"[Sau {self.ai_step_count} bước][RULE-BASED DỪNG] "
                    "Không còn nước đi chắc chắn theo luật cơ bản. "
                    "Đây là thời điểm cần chuyển sang Hybrid BFS/DFS Search."
                )
            else:
                self.set_status("AI không tìm thấy nước đi tiếp theo.")
            return False

        self.ai.execute_move(move)
        self.ai_step_count += 1
        self._update_board_display()

        if self.game.game_over:
            if self.game.won:
                self.btn_smiley.config(text="😎")
                self.set_status(
                    f"[Bước {self.ai_step_count}][{move.method}] CHIẾN THẮNG. "
                    f"AI hoàn thành bàn cờ trong {self.game.get_elapsed_time()} giây. "
                    f"Nước cuối: {move.reason}"
                )
            else:
                self.btn_smiley.config(text="😵")
                self.set_status(
                    f"[Bước {self.ai_step_count}][{move.method}] AI mở ô "
                    f"({move.row}, {move.col}) và gặp mìn. P(mìn) trước khi mở: "
                    f"{move.probability:.1%}. {move.reason}"
                )
        else:
            self.set_status(
                f"[Bước {self.ai_step_count}][{move.method}] "
                f"{self._action_text(move)} ({move.row}, {move.col}) | "
                f"P(mìn)={move.probability:.1%}. {move.reason}"
            )

        return True

    def toggle_autoplay(self):
        if self.is_auto_playing:
            self.is_auto_playing = False
            self.btn_autoplay.config(text="AI tự giải", bg="#EDE7F6")
            self.set_status("Đã tạm dừng AI tự giải.")
            return

        if self.game.game_over:
            self.restart_game()

        self.is_auto_playing = True
        self.btn_autoplay.config(text="Dừng AI", bg="#FFCDD2")
        mode = self.ai_mode_var.get()
        self.set_status(
            f"Bắt đầu AI tự giải. Mode={mode}, Search={self.search_algo_var.get()}."
        )
        self._run_autoplay_step()

    def _run_autoplay_step(self):
        if not self.is_auto_playing or self.game.game_over:
            self.is_auto_playing = False
            self.btn_autoplay.config(text="AI tự giải", bg="#EDE7F6")
            return

        moved = self.step_ai()
        if not moved:
            self.is_auto_playing = False
            self.btn_autoplay.config(text="AI tự giải", bg="#EDE7F6")
            return

        if not self.game.game_over and self.is_auto_playing:
            self.root.after(self.auto_play_delay_ms, self._run_autoplay_step)
        else:
            self.is_auto_playing = False
            self.btn_autoplay.config(text="AI tự giải", bg="#EDE7F6")

    # ------------------------------------------------------------------
    # Game configuration
    # ------------------------------------------------------------------
    def _update_timer(self):
        if not self.game.game_over and not self.game.first_click:
            self.lbl_timer.config(text=f"Time {self.game.get_elapsed_time():03d}")
        self.root.after(1000, self._update_timer)

    def change_difficulty(self, rows: int, cols: int, mines: int, seed=None):
        if self.is_auto_playing:
            self.toggle_autoplay()

        self.current_rows = rows
        self.current_cols = cols
        self.current_mines = mines
        self.current_seed = seed
        self.restart_game()

    def load_search_challenge(self):
        """
        Load a reproducible 25x30 board.

        With seed=4, classic Rule-based solving reaches a genuine stall before
        the board is complete. Hybrid mode then needs BFS/DFS search to continue.
        """
        self.ai_mode_var.set(MinesweeperAI.HYBRID)
        self.current_rows = self.CHALLENGE_ROWS
        self.current_cols = self.CHALLENGE_COLS
        self.current_mines = self.CHALLENGE_MINES
        self.current_seed = self.CHALLENGE_SEED
        self.restart_game(
            status_message=(
                "25x30 Search Challenge đã nạp (150 mìn, seed cố định = 4). "
                "AI Hybrid sẽ dùng Rule-based trước; khi luật cơ bản thật sự bị kẹt, "
                f"nó tự chuyển sang {self.search_algo_var.get()} Search."
            )
        )

    def restart_game(self, status_message=None):
        if self.is_auto_playing:
            self.is_auto_playing = False
            self.btn_autoplay.config(text="AI tự giải", bg="#EDE7F6")

        # Rebuild the board widget only when the number of rows/columns really
        # changes. A normal New Game/F2 reuses the existing buttons, so the
        # top-level window never collapses or flashes.
        old_rows = len(self.buttons) if hasattr(self, "buttons") else 0
        old_cols = len(self.buttons[0]) if old_rows else 0
        size_changed = (old_rows != self.current_rows or old_cols != self.current_cols)

        self.hint_cells.clear()
        self.ai_step_count = 0
        self.btn_smiley.config(text="😊")

        self.game.reset(
            self.current_rows,
            self.current_cols,
            self.current_mines,
            self.search_algo_var.get(),
            random_seed=self.current_seed,
        )
        self.ai = MinesweeperAI(self.game)
        self.lbl_timer.config(text="Time 000")

        if size_changed:
            self._build_board()
        else:
            # Same board dimensions: reuse the current widgets and restore their
            # initial visual state. This prevents any destroy/recreate flicker.
            large_board = self.current_rows >= 20 or self.current_cols >= 20
            border = 1 if large_board else 2
            for row in self.buttons:
                for btn in row:
                    btn.config(
                        text="",
                        bg=self.BG_UNREVEALED,
                        fg="#000000",
                        relief=tk.RAISED,
                        bd=border,
                    )

        self._update_board_display()

        if status_message is None:
            status_message = (
                f"Ván mới {self.current_rows}x{self.current_cols}, "
                f"{self.current_mines} mìn. AI={self.ai_mode_var.get()}, "
                f"Search={self.search_algo_var.get()}."
            )
        self.set_status(status_message)

        # Large boards get the largest practical viewport automatically.
        # Smaller boards keep the user's current normal/maximized/fullscreen state.
        if size_changed:
            if self.current_rows >= 20 or self.current_cols >= 20:
                self.root.after_idle(self._maximize_large_board_if_needed)
            else:
                self._ensure_board_fits_when_normal()

        self.root.after_idle(self._sync_board_viewport)
        self.root.after_idle(self._apply_responsive_board_style)

    def _open_custom_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Tùy chỉnh bàn cờ")
        dialog.geometry("280x190")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Số hàng (5 - 30):").grid(
            row=0, column=0, padx=10, pady=5, sticky=tk.W
        )
        entry_r = tk.Entry(dialog, width=8)
        entry_r.insert(0, str(self.current_rows))
        entry_r.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Số cột (5 - 30):").grid(
            row=1, column=0, padx=10, pady=5, sticky=tk.W
        )
        entry_c = tk.Entry(dialog, width=8)
        entry_c.insert(0, str(self.current_cols))
        entry_c.grid(row=1, column=1, padx=10, pady=5)

        tk.Label(dialog, text="Số mìn:").grid(
            row=2, column=0, padx=10, pady=5, sticky=tk.W
        )
        entry_m = tk.Entry(dialog, width=8)
        entry_m.insert(0, str(self.current_mines))
        entry_m.grid(row=2, column=1, padx=10, pady=5)

        def apply_custom():
            try:
                rows = int(entry_r.get())
                cols = int(entry_c.get())
                mines = int(entry_m.get())
                if not (5 <= rows <= 30 and 5 <= cols <= 30):
                    messagebox.showerror(
                        "Lỗi", "Kích thước bàn cờ phải từ 5 đến 30."
                    )
                    return
                if not (1 <= mines < rows * cols):
                    messagebox.showerror(
                        "Lỗi", f"Số mìn phải từ 1 đến {rows * cols - 1}."
                    )
                    return
                dialog.destroy()
                self.change_difficulty(rows, cols, mines)
            except ValueError:
                messagebox.showerror("Lỗi", "Vui lòng nhập số nguyên hợp lệ.")

        tk.Button(
            dialog,
            text="Đồng ý",
            command=apply_custom,
            bg="#C8E6C9",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=3, column=0, columnspan=2, pady=10)

    def _show_about(self):
        info = (
            "TRƯỜNG ĐH BÁCH KHOA - ĐHQG TP.HCM\n"
            "Khoa Khoa học và Kỹ thuật Máy tính\n"
            "Môn: Nhập môn Trí Tuệ Nhân Tạo (CO3061)\n"
            "GVHD: TS. Nguyễn Quốc Minh\n\n"
            "BÀI TẬP LỚN 1 - TOPIC 1: MINESWEEPER\n\n"
            "AI solver:\n"
            "- Rule-based: 2 luật Minesweeper cơ bản.\n"
            "- Hybrid: Rule-based trước, BFS/DFS constraint search khi bị kẹt.\n"
            "- 25x30 Search Challenge: seed cố định để tái hiện tình huống Rule-based bị kẹt.\n\n"
            "Nhóm sinh viên thực hiện:\n"
            "1. Trần Bá Minh Quân - MSSV: 2353015\n"
            "2. Đặng Thế Lâm Anh - MSSV: 2352027\n"
            "3. Nguyễn Trần Hoàng Khánh - MSSV: 2352530\n"
            "4. Hồng Chấn Phước - MSSV: 2352963\n"
            "5. Hồ Gia Bảo - MSSV: 2352089\n"
        )
        messagebox.showinfo("Thông tin đồ án", info)

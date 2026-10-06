"""
game_logic.py - Core Minesweeper logic with BFS and DFS Flood Fill.
Author: Group Students (CO3061) - HCMUT
Course: Introduction to Artificial Intelligence (CO3061) - HCMUT
"""

import random
from collections import deque
import time


class Cell:
    """Represents a single cell on the Minesweeper board."""
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col
        self.is_mine = False
        self.is_revealed = False
        self.is_flagged = False
        self.neighbor_mines = 0

    def reset(self):
        self.is_mine = False
        self.is_revealed = False
        self.is_flagged = False
        self.neighbor_mines = 0


class MinesweeperGame:
    """Manages the state and operations of the Minesweeper game."""
    def __init__(self, rows: int = 9, cols: int = 9, num_mines: int = 10, flood_algorithm: str = "BFS", random_seed=None):
        self.rows = rows
        self.cols = cols
        self.num_mines = min(num_mines, rows * cols - 1)
        self.flood_algorithm = flood_algorithm.upper()  # 'BFS' or 'DFS'
        self.random_seed = random_seed
        self._rng = random.Random(random_seed) if random_seed is not None else random.Random()
        
        self.board = [[Cell(r, c) for c in range(self.cols)] for r in range(self.rows)]
        self.game_over = False
        self.won = False
        self.first_click = True
        self.flags_placed = 0
        self.revealed_count = 0
        self.start_time = None
        self.end_time = None
        self.last_flood_revealed = []
        self.last_algorithm_used = self.flood_algorithm

    def reset(self, rows: int = None, cols: int = None, num_mines: int = None, flood_algorithm: str = None, random_seed=None):
        """Resets the game with optional new dimensions or settings."""
        if rows is not None:
            self.rows = rows
        if cols is not None:
            self.cols = cols
        if num_mines is not None:
            self.num_mines = min(num_mines, self.rows * self.cols - 1)
        if flood_algorithm is not None:
            self.flood_algorithm = flood_algorithm.upper()
        self.random_seed = random_seed
        self._rng = random.Random(random_seed) if random_seed is not None else random.Random()

        self.board = [[Cell(r, c) for c in range(self.cols)] for r in range(self.rows)]
        self.game_over = False
        self.won = False
        self.first_click = True
        self.flags_placed = 0
        self.revealed_count = 0
        self.start_time = None
        self.end_time = None
        self.last_flood_revealed = []
        self.last_algorithm_used = self.flood_algorithm

    def get_neighbors(self, r: int, c: int):
        """Returns valid adjacent neighbor coordinates (horizontal, vertical, diagonal)."""
        neighbors = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    neighbors.append((nr, nc))
        return neighbors

    def _place_mines(self, safe_r: int, safe_c: int):
        """
        Places mines randomly while guaranteeing that the first-clicked cell
        (and ideally its immediate neighbors if space permits) is safe.
        """
        forbidden = {(safe_r, safe_c)}
        # Try to keep 8 neighbors safe as well if board has enough cells
        if self.rows * self.cols - self.num_mines >= 9:
            forbidden.update(self.get_neighbors(safe_r, safe_c))

        all_coords = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in forbidden]
        
        # If not enough cells outside forbidden set, relax forbidden to only (safe_r, safe_c)
        if len(all_coords) < self.num_mines:
            all_coords = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) != (safe_r, safe_c)]
            
        mine_coords = set(self._rng.sample(all_coords, self.num_mines))
        for r, c in mine_coords:
            self.board[r][c].is_mine = True

        # Calculate neighbor mine count for each non-mine cell
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.board[r][c].is_mine:
                    self.board[r][c].neighbor_mines = sum(
                        1 for nr, nc in self.get_neighbors(r, c) if self.board[nr][nc].is_mine
                    )

    def reveal_cell(self, r: int, c: int) -> bool:
        """
        Reveals cell (r, c).
        Returns True if successful and game continues, False if game over (loss).
        """
        if self.game_over or self.board[r][c].is_flagged or self.board[r][c].is_revealed:
            return not self.game_over

        if self.first_click:
            self.start_time = time.time()
            self._place_mines(r, c)
            self.first_click = False

        cell = self.board[r][c]
        if cell.is_mine:
            # Hit a mine: Game Over (Loss)
            self.game_over = True
            self.won = False
            self.end_time = time.time()
            # Reveal all mines for visual feedback
            for row in self.board:
                for cl in row:
                    if cl.is_mine:
                        cl.is_revealed = True
            return False

        # Reveal safe cell
        cell.is_revealed = True
        self.revealed_count += 1

        # If cell has 0 neighboring mines, flood fill to open connected empty cells
        if cell.neighbor_mines == 0:
            if self.flood_algorithm == "DFS":
                self.last_flood_revealed = self._flood_fill_dfs(r, c)
            else:
                self.last_flood_revealed = self._flood_fill_bfs(r, c)
            self.last_algorithm_used = self.flood_algorithm
        else:
            self.last_flood_revealed = [(r, c)]

        # Check win condition
        total_safe_cells = self.rows * self.cols - self.num_mines
        if self.revealed_count == total_safe_cells:
            self.game_over = True
            self.won = True
            self.end_time = time.time()
            # Flag all remaining unrevealed mines automatically
            for row in self.board:
                for cl in row:
                    if cl.is_mine:
                        cl.is_flagged = True
            self.flags_placed = self.num_mines

        return True

    def _flood_fill_bfs(self, start_r: int, start_c: int):
        """
        BFS algorithm for cascading empty cells (neighbor_mines == 0).
        Uses a FIFO queue (deque).
        """
        revealed_list = [(start_r, start_c)]
        queue = deque([(start_r, start_c)])
        visited = {(start_r, start_c)}

        while queue:
            curr_r, curr_c = queue.popleft()
            curr_cell = self.board[curr_r][curr_c]

            # If current cell has 0 neighboring mines, explore its neighbors
            if curr_cell.neighbor_mines == 0:
                for nr, nc in self.get_neighbors(curr_r, curr_c):
                    if (nr, nc) not in visited:
                        visited.add((nr, nc))
                        neighbor = self.board[nr][nc]
                        if not neighbor.is_flagged and not neighbor.is_revealed and not neighbor.is_mine:
                            neighbor.is_revealed = True
                            self.revealed_count += 1
                            revealed_list.append((nr, nc))
                            if neighbor.neighbor_mines == 0:
                                queue.append((nr, nc))

        return revealed_list

    def _flood_fill_dfs(self, start_r: int, start_c: int):
        """
        DFS algorithm for cascading empty cells (neighbor_mines == 0).
        Uses an explicit LIFO stack to prevent call-stack overflow.
        """
        revealed_list = [(start_r, start_c)]
        stack = [(start_r, start_c)]
        visited = {(start_r, start_c)}

        while stack:
            curr_r, curr_c = stack.pop()
            curr_cell = self.board[curr_r][curr_c]

            if curr_cell.neighbor_mines == 0:
                for nr, nc in self.get_neighbors(curr_r, curr_c):
                    if (nr, nc) not in visited:
                        visited.add((nr, nc))
                        neighbor = self.board[nr][nc]
                        if not neighbor.is_flagged and not neighbor.is_revealed and not neighbor.is_mine:
                            neighbor.is_revealed = True
                            self.revealed_count += 1
                            revealed_list.append((nr, nc))
                            if neighbor.neighbor_mines == 0:
                                stack.append((nr, nc))

        return revealed_list

    def toggle_flag(self, r: int, c: int) -> bool:
        """Toggles a flag on an unrevealed cell."""
        if self.game_over or self.board[r][c].is_revealed:
            return False

        cell = self.board[r][c]
        if cell.is_flagged:
            cell.is_flagged = False
            self.flags_placed -= 1
        else:
            cell.is_flagged = True
            self.flags_placed += 1
        return True

    def get_elapsed_time(self) -> int:
        """Returns elapsed game time in seconds."""
        if self.start_time is None:
            return 0
        if self.end_time is not None:
            return int(self.end_time - self.start_time)
        return int(time.time() - self.start_time)

    def get_remaining_mines(self) -> int:
        """Returns remaining mines count (total mines - flags placed)."""
        return self.num_mines - self.flags_placed

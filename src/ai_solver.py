"""
ai_solver.py - AI agent for Minesweeper.

The solver is intentionally split into two layers:
1. RULES: classic deterministic Minesweeper rules only.
2. HYBRID: use RULES first; when the rules are stuck, use BFS/DFS
   to search a bounded constraint-state space on the current frontier.

BFS/DFS here is used as an AI search fallback, not only as the game's
zero-cell flood-fill implementation.
"""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from game_logic import MinesweeperGame

Coord = Tuple[int, int]
Constraint = Tuple[Set[Coord], int, Coord]


class Move:
    """Represents one AI action."""

    REVEAL = "REVEAL"
    FLAG = "FLAG"
    GUESS = "GUESS"

    def __init__(
        self,
        action: str,
        row: int,
        col: int,
        reason: str,
        probability: float = 0.0,
        method: str = "",
    ):
        self.action = action
        self.row = row
        self.col = col
        self.reason = reason
        self.probability = probability
        self.method = method

    def __repr__(self):
        return (
            f"Move({self.action} at ({self.row}, {self.col}), "
            f"P(mine)={self.probability:.1%}, method='{self.method}', "
            f"reason='{self.reason}')"
        )


class MinesweeperAI:
    """Rule-based solver with BFS/DFS constraint-search fallback."""

    RULES_ONLY = "RULES"
    HYBRID = "HYBRID"

    def __init__(self, game: MinesweeperGame):
        self.game = game
        self.last_search_stats: Dict[str, object] = {}

    # ------------------------------------------------------------------
    # Board/frontier extraction
    # ------------------------------------------------------------------
    def get_cell_frontier_info(self):
        """
        Extract visible constraints from the current board.

        Returns:
        - revealed numbered cells that still touch unknown cells
        - unknown/unflagged neighbors for each numbered cell
        - remaining mines needed around each numbered cell
        - all frontier cells
        - all isolated unknown cells
        """
        revealed_numbered: List[Coord] = []
        unrevealed_neighbors: Dict[Coord, Set[Coord]] = {}
        remaining_mines_needed: Dict[Coord, int] = {}
        all_frontier_cells: Set[Coord] = set()

        for r in range(self.game.rows):
            for c in range(self.game.cols):
                cell = self.game.board[r][c]
                if not cell.is_revealed or cell.neighbor_mines <= 0:
                    continue

                neighbors = self.game.get_neighbors(r, c)
                flagged = {
                    pos
                    for pos in neighbors
                    if self.game.board[pos[0]][pos[1]].is_flagged
                }
                unknown = {
                    pos
                    for pos in neighbors
                    if not self.game.board[pos[0]][pos[1]].is_revealed
                    and not self.game.board[pos[0]][pos[1]].is_flagged
                }

                if unknown:
                    revealed_numbered.append((r, c))
                    unrevealed_neighbors[(r, c)] = unknown
                    remaining_mines_needed[(r, c)] = (
                        cell.neighbor_mines - len(flagged)
                    )
                    all_frontier_cells.update(unknown)

        all_unrevealed = {
            (r, c)
            for r in range(self.game.rows)
            for c in range(self.game.cols)
            if not self.game.board[r][c].is_revealed
            and not self.game.board[r][c].is_flagged
        }
        all_isolated_cells = all_unrevealed - all_frontier_cells

        return (
            revealed_numbered,
            unrevealed_neighbors,
            remaining_mines_needed,
            all_frontier_cells,
            all_isolated_cells,
        )

    # ------------------------------------------------------------------
    # Classic rule-based Minesweeper
    # ------------------------------------------------------------------
    def find_opening_move(self) -> Optional[Move]:
        """Use one deterministic opening so a rule-only solver can start."""
        if not self.game.first_click:
            return None

        row = self.game.rows // 2
        col = self.game.cols // 2
        return Move(
            Move.REVEAL,
            row,
            col,
            "Bước mở đầu: mở ô trung tâm để tạo vùng thông tin ban đầu.",
            probability=0.0,
            method="OPENING",
        )

    def find_rule_based_move(self) -> Optional[Move]:
        """
        Classic Minesweeper rules.

        Rule 1 - SAFE:
            clue - flagged == 0
            => every remaining hidden neighbor is safe.

        Rule 2 - MINE:
            clue - flagged == number of hidden neighbors
            => every remaining hidden neighbor is a mine.
        """
        rev_numbered, unrev_nbrs, needed_dict, _, _ = self.get_cell_frontier_info()

        # Stable sorting makes demonstrations repeatable.
        for r, c in sorted(rev_numbered):
            needed = needed_dict[(r, c)]
            unknown = sorted(unrev_nbrs[(r, c)])
            if needed == 0 and unknown:
                target = unknown[0]
                return Move(
                    Move.REVEAL,
                    target[0],
                    target[1],
                    (
                        f"Rule SAFE: ô ({r}, {c}) đã đủ số mìn/cờ. "
                        f"Vì vậy ô ({target[0]}, {target[1]}) chắc chắn an toàn."
                    ),
                    probability=0.0,
                    method="RULE",
                )

        for r, c in sorted(rev_numbered):
            needed = needed_dict[(r, c)]
            unknown = sorted(unrev_nbrs[(r, c)])
            if unknown and needed == len(unknown):
                target = unknown[0]
                return Move(
                    Move.FLAG,
                    target[0],
                    target[1],
                    (
                        f"Rule MINE: ô ({r}, {c}) còn thiếu {needed} mìn và "
                        f"đúng {len(unknown)} ô chưa biết. Ô ({target[0]}, {target[1]}) "
                        "chắc chắn là mìn."
                    ),
                    probability=1.0,
                    method="RULE",
                )

        return None

    # Backward-compatible name used by older code/reports.
    def find_deterministic_move(self) -> Optional[Move]:
        return self.find_rule_based_move()

    # ------------------------------------------------------------------
    # Constraint search used only when rules are stuck
    # ------------------------------------------------------------------
    def _build_constraints(self) -> List[Constraint]:
        rev_numbered, unrev_nbrs, needed_dict, _, _ = self.get_cell_frontier_info()
        constraints: List[Constraint] = []

        for clue_pos in sorted(rev_numbered):
            variables = set(unrev_nbrs[clue_pos])
            needed = needed_dict[clue_pos]
            # Ignore contradictory constraints caused by an invalid manual flag state.
            if variables and 0 <= needed <= len(variables):
                constraints.append((variables, needed, clue_pos))

        return constraints

    def _build_local_search_region(
        self, constraints: List[Constraint], max_variables: int = 15
    ) -> Tuple[List[Coord], List[Constraint]]:
        """
        Select a connected local frontier small enough for exact BFS/DFS search.

        The region starts from the tightest visible constraint and greedily adds
        overlapping constraints while the union stays within max_variables.
        """
        if not constraints:
            return [], []

        ordered = sorted(
            constraints,
            key=lambda item: (len(item[0]), abs(len(item[0]) / 2 - item[1]), item[2]),
        )
        seed = ordered[0]
        selected: List[Constraint] = [seed]
        variables: Set[Coord] = set(seed[0])

        changed = True
        while changed:
            changed = False
            candidates = []
            for constraint in ordered:
                if constraint in selected:
                    continue
                cells, _, clue = constraint
                overlap = len(cells & variables)
                if overlap == 0:
                    continue
                new_union = variables | cells
                if len(new_union) <= max_variables:
                    candidates.append((len(new_union) - len(variables), -overlap, clue, constraint))

            if candidates:
                candidates.sort(key=lambda item: (item[0], item[1], item[2]))
                chosen = candidates[0][3]
                selected.append(chosen)
                variables.update(chosen[0])
                changed = True

        return sorted(variables), selected

    @staticmethod
    def _state_is_feasible(
        assignment: Tuple[int, ...],
        constraints_indexed: List[Tuple[Tuple[int, ...], int]],
    ) -> bool:
        assigned_count = len(assignment)

        for indices, needed in constraints_indexed:
            mines_assigned = 0
            unknown_count = 0
            for idx in indices:
                if idx < assigned_count:
                    mines_assigned += assignment[idx]
                else:
                    unknown_count += 1

            if mines_assigned > needed:
                return False
            if mines_assigned + unknown_count < needed:
                return False

        return True

    def _enumerate_region_solutions(
        self,
        variables: List[Coord],
        constraints: List[Constraint],
        algorithm: str,
    ) -> Tuple[int, Dict[Coord, int], int]:
        """
        Enumerate all assignments consistent with the selected local constraints.

        Each state is a partial 0/1 assignment over frontier cells:
        0 = safe, 1 = mine.
        BFS uses a FIFO queue, DFS uses a LIFO stack.
        """
        if not variables:
            return 0, {}, 0

        index_of = {cell: idx for idx, cell in enumerate(variables)}
        indexed_constraints: List[Tuple[Tuple[int, ...], int]] = []
        for cells, needed, _ in constraints:
            indices = tuple(sorted(index_of[cell] for cell in cells if cell in index_of))
            if indices:
                indexed_constraints.append((indices, needed))

        algorithm = algorithm.upper()
        if algorithm not in ("BFS", "DFS"):
            algorithm = "BFS"

        states_explored = 0
        solution_count = 0
        mine_frequency = {cell: 0 for cell in variables}

        if algorithm == "BFS":
            frontier = deque([tuple()])
            pop_state = frontier.popleft
            push_state = frontier.append
        else:
            frontier = [tuple()]
            pop_state = frontier.pop
            push_state = frontier.append

        while frontier:
            assignment = pop_state()
            states_explored += 1

            if len(assignment) == len(variables):
                if self._state_is_feasible(assignment, indexed_constraints):
                    solution_count += 1
                    for idx, value in enumerate(assignment):
                        if value == 1:
                            mine_frequency[variables[idx]] += 1
                continue

            # Branch 0 first so BFS/DFS traces are deterministic.
            safe_child = assignment + (0,)
            if self._state_is_feasible(safe_child, indexed_constraints):
                push_state(safe_child)

            mine_child = assignment + (1,)
            if self._state_is_feasible(mine_child, indexed_constraints):
                push_state(mine_child)

        return solution_count, mine_frequency, states_explored

    def _information_gain(self, cell: Coord) -> int:
        return sum(
            1
            for nr, nc in self.game.get_neighbors(cell[0], cell[1])
            if not self.game.board[nr][nc].is_revealed
            and not self.game.board[nr][nc].is_flagged
        )

    def find_search_move(self, algorithm: str = "BFS") -> Optional[Move]:
        """Use BFS/DFS exact local constraint search after rule-based logic stalls."""
        algorithm = algorithm.upper()
        if algorithm not in ("BFS", "DFS"):
            algorithm = "BFS"

        constraints = self._build_constraints()
        variables, local_constraints = self._build_local_search_region(constraints)

        if variables and local_constraints:
            solution_count, mine_frequency, states_explored = self._enumerate_region_solutions(
                variables, local_constraints, algorithm
            )
            self.last_search_stats = {
                "algorithm": algorithm,
                "variables": len(variables),
                "constraints": len(local_constraints),
                "solutions": solution_count,
                "states": states_explored,
            }

            if solution_count > 0:
                safe_cells = [cell for cell in variables if mine_frequency[cell] == 0]
                mine_cells = [
                    cell for cell in variables if mine_frequency[cell] == solution_count
                ]

                if safe_cells:
                    target = max(sorted(safe_cells), key=self._information_gain)
                    return Move(
                        Move.REVEAL,
                        target[0],
                        target[1],
                        (
                            f"{algorithm} Search: Rule-based đã bị kẹt. Duyệt "
                            f"{states_explored} trạng thái / {solution_count} nghiệm hợp lệ; "
                            f"ô ({target[0]}, {target[1]}) an toàn trong mọi nghiệm."
                        ),
                        probability=0.0,
                        method=algorithm,
                    )

                if mine_cells:
                    target = sorted(mine_cells)[0]
                    return Move(
                        Move.FLAG,
                        target[0],
                        target[1],
                        (
                            f"{algorithm} Search: Rule-based đã bị kẹt. Duyệt "
                            f"{states_explored} trạng thái / {solution_count} nghiệm hợp lệ; "
                            f"ô ({target[0]}, {target[1]}) là mìn trong mọi nghiệm."
                        ),
                        probability=1.0,
                        method=algorithm,
                    )

                probabilities = {
                    cell: mine_frequency[cell] / solution_count for cell in variables
                }
                min_probability = min(probabilities.values())
                candidates = [
                    cell
                    for cell, probability in probabilities.items()
                    if abs(probability - min_probability) < 1e-12
                ]
                target = max(sorted(candidates), key=self._information_gain)
                return Move(
                    Move.GUESS,
                    target[0],
                    target[1],
                    (
                        f"{algorithm} Search: không có nước đi chắc chắn. Sau "
                        f"{states_explored} trạng thái / {solution_count} nghiệm, chọn ô "
                        f"({target[0]}, {target[1]}) có rủi ro thấp nhất."
                    ),
                    probability=min_probability,
                    method=algorithm,
                )

        # If no local constraint region is available, use a probability heuristic
        # only to keep Hybrid mode moving.
        return self.find_heuristic_guess_move(prefix=f"{algorithm} fallback")

    # ------------------------------------------------------------------
    # Heuristic fallback for unconstrained/ambiguous situations
    # ------------------------------------------------------------------
    def find_heuristic_guess_move(self, prefix: str = "Heuristic") -> Optional[Move]:
        (
            _,
            unrev_nbrs,
            needed_dict,
            frontier_cells,
            isolated_cells,
        ) = self.get_cell_frontier_info()

        opening = self.find_opening_move()
        if opening:
            return opening

        cell_probabilities: Dict[Coord, float] = {}

        for cell in sorted(frontier_cells):
            max_probability = 0.0
            for clue_pos, unknown in unrev_nbrs.items():
                if cell in unknown and unknown:
                    local_probability = max(
                        0.0,
                        min(1.0, needed_dict[clue_pos] / len(unknown)),
                    )
                    max_probability = max(max_probability, local_probability)
            cell_probabilities[cell] = max_probability

        all_unknown_count = len(frontier_cells) + len(isolated_cells)
        remaining_mines = max(0, self.game.get_remaining_mines())

        if isolated_cells and all_unknown_count > 0:
            estimated_frontier_mines = sum(cell_probabilities.values())
            remaining_for_isolated = max(
                0.0, remaining_mines - estimated_frontier_mines
            )
            isolated_probability = min(
                1.0, remaining_for_isolated / len(isolated_cells)
            )
            for cell in sorted(isolated_cells):
                cell_probabilities[cell] = isolated_probability

        if not cell_probabilities:
            return None

        min_probability = min(cell_probabilities.values())
        candidates = [
            cell
            for cell, probability in cell_probabilities.items()
            if abs(probability - min_probability) < 1e-12
        ]
        target = max(sorted(candidates), key=self._information_gain)

        return Move(
            Move.GUESS,
            target[0],
            target[1],
            (
                f"{prefix}: chọn ô ({target[0]}, {target[1]}) có xác suất mìn "
                f"ước lượng thấp nhất và độ lợi thông tin cao."
            ),
            probability=min_probability,
            method="HEURISTIC",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_next_move(
        self,
        strategy: str = HYBRID,
        search_algorithm: str = "BFS",
    ) -> Optional[Move]:
        """
        Return the next move.

        RULES:
            Opening -> classic deterministic rules -> STOP when rules are stuck.

        HYBRID:
            Opening -> classic deterministic rules -> BFS/DFS search fallback.
        """
        if self.game.game_over:
            return None

        opening = self.find_opening_move()
        if opening:
            return opening

        move = self.find_rule_based_move()
        if move:
            return move

        strategy = strategy.upper()
        if strategy == self.RULES_ONLY:
            return None

        return self.find_search_move(search_algorithm)

    def execute_move(self, move: Move) -> bool:
        """Execute a Move on the game board."""
        if move.action == Move.FLAG:
            return self.game.toggle_flag(move.row, move.col)
        if move.action in (Move.REVEAL, Move.GUESS):
            return self.game.reveal_cell(move.row, move.col)
        return False

"""
benchmark.py - Automated experiments for the Rule-based / Hybrid Minesweeper AI.
"""

import sys
import time

from ai_solver import MinesweeperAI, Move
from game_logic import MinesweeperGame

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run_single_simulation(
    rows: int,
    cols: int,
    num_mines: int,
    ai_mode: str = MinesweeperAI.HYBRID,
    search_algo: str = "BFS",
    seed=None,
):
    """Run one automated game and return solver statistics."""
    game = MinesweeperGame(
        rows,
        cols,
        num_mines,
        flood_algorithm=search_algo,
        random_seed=seed,
    )
    ai = MinesweeperAI(game)

    moves_count = 0
    guesses_count = 0
    search_steps = 0
    rule_steps = 0
    start_t = time.perf_counter()
    stalled = False

    while not game.game_over:
        move = ai.get_next_move(ai_mode, search_algo)
        if not move:
            stalled = True
            break

        moves_count += 1
        if move.method == "RULE":
            rule_steps += 1
        if move.method in ("BFS", "DFS", "HEURISTIC"):
            search_steps += 1
        if move.action == Move.GUESS:
            guesses_count += 1

        ai.execute_move(move)

    duration_ms = (time.perf_counter() - start_t) * 1000
    return {
        "won": game.won,
        "stalled": stalled,
        "moves": moves_count,
        "rule_steps": rule_steps,
        "search_steps": search_steps,
        "guesses": guesses_count,
        "time_ms": duration_ms,
        "revealed": game.revealed_count,
    }


def run_benchmark(num_games: int = 100):
    """Benchmark normal random boards with both AI strategies."""
    configs = [
        {
            "name": "9x9 Rule-only",
            "rows": 9,
            "cols": 9,
            "mines": 10,
            "mode": MinesweeperAI.RULES_ONLY,
            "algo": "BFS",
        },
        {
            "name": "9x9 Hybrid BFS",
            "rows": 9,
            "cols": 9,
            "mines": 10,
            "mode": MinesweeperAI.HYBRID,
            "algo": "BFS",
        },
        {
            "name": "9x9 Hybrid DFS",
            "rows": 9,
            "cols": 9,
            "mines": 10,
            "mode": MinesweeperAI.HYBRID,
            "algo": "DFS",
        },
        {
            "name": "16x16 Hybrid BFS",
            "rows": 16,
            "cols": 16,
            "mines": 40,
            "mode": MinesweeperAI.HYBRID,
            "algo": "BFS",
        },
    ]

    print("=" * 78)
    print(f"MINESWEEPER AI BENCHMARK - {num_games} ván/cấu hình")
    print("=" * 78)

    results_summary = []
    for cfg in configs:
        totals = {
            "wins": 0,
            "stalls": 0,
            "moves": 0,
            "search_steps": 0,
            "guesses": 0,
            "time_ms": 0.0,
        }

        for _ in range(num_games):
            result = run_single_simulation(
                cfg["rows"],
                cfg["cols"],
                cfg["mines"],
                cfg["mode"],
                cfg["algo"],
            )
            totals["wins"] += int(result["won"])
            totals["stalls"] += int(result["stalled"])
            totals["moves"] += result["moves"]
            totals["search_steps"] += result["search_steps"]
            totals["guesses"] += result["guesses"]
            totals["time_ms"] += result["time_ms"]

        summary = {
            "name": cfg["name"],
            "win_rate": totals["wins"] / num_games * 100,
            "stall_rate": totals["stalls"] / num_games * 100,
            "avg_moves": totals["moves"] / num_games,
            "avg_search_steps": totals["search_steps"] / num_games,
            "avg_guesses": totals["guesses"] / num_games,
            "avg_time_ms": totals["time_ms"] / num_games,
        }
        results_summary.append(summary)

        print(
            f"{cfg['name']:<22} | Win={summary['win_rate']:5.1f}% "
            f"| Stall={summary['stall_rate']:5.1f}% "
            f"| Moves={summary['avg_moves']:6.1f} "
            f"| Search={summary['avg_search_steps']:5.1f} "
            f"| Guess={summary['avg_guesses']:5.1f} "
            f"| {summary['avg_time_ms']:8.2f} ms"
        )

    print("=" * 78)
    return results_summary


def demonstrate_25x30_challenge(search_algo: str = "BFS"):
    """Show that the fixed 25x30 board stalls with Rules but continues in Hybrid."""
    print("\n25x30 SEARCH CHALLENGE (150 mines, seed=4)")
    print("-" * 78)

    rules = run_single_simulation(
        25,
        30,
        150,
        ai_mode=MinesweeperAI.RULES_ONLY,
        search_algo=search_algo,
        seed=4,
    )
    hybrid = run_single_simulation(
        25,
        30,
        150,
        ai_mode=MinesweeperAI.HYBRID,
        search_algo=search_algo,
        seed=4,
    )

    print(
        f"Rule-only: won={rules['won']}, stalled={rules['stalled']}, "
        f"moves={rules['moves']}, revealed={rules['revealed']}"
    )
    print(
        f"Hybrid {search_algo}: won={hybrid['won']}, stalled={hybrid['stalled']}, "
        f"moves={hybrid['moves']}, search_steps={hybrid['search_steps']}, "
        f"guesses={hybrid['guesses']}"
    )
    return {"rules": rules, "hybrid": hybrid}


if __name__ == "__main__":
    run_benchmark(100)
    demonstrate_25x30_challenge("BFS")

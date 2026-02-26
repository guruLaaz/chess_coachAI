from chessgameanalyzer import ChessGameAnalyzer
from helpers import make_chess_game


class TestSummarize:
    def test_empty_games(self):
        analyzer = ChessGameAnalyzer("player", [])
        assert analyzer.summarize() == {}

    def test_all_wins_as_white(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="checkmate"),
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="time"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["total_games"] == 2
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["draws"] == 0
        assert stats["win_percent"] == 100.0

    def test_all_wins_as_black(self):
        games = [
            make_chess_game(my_color="black", white_result="lose", black_result="win",
                            termination="checkmate"),
            make_chess_game(my_color="black", white_result="lose", black_result="win",
                            termination="time"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["total_games"] == 2
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["draws"] == 0
        assert stats["win_percent"] == 100.0

    def test_all_losses_as_white(self):
        games = [
            make_chess_game(my_color="white", white_result="lose", black_result="win",
                            termination="checkmate"),
            make_chess_game(my_color="white", white_result="timeout", black_result="win",
                            termination="time"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["wins"] == 0
        assert stats["losses"] == 2
        assert stats["win_percent"] == 0.0

    def test_all_losses_as_black(self):
        games = [
            make_chess_game(my_color="black", white_result="win", black_result="checkmated",
                            termination="checkmate"),
            make_chess_game(my_color="black", white_result="win", black_result="timeout",
                            termination="time"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["wins"] == 0
        assert stats["losses"] == 2
        assert stats["win_percent"] == 0.0

    def test_mix_of_results_both_colors(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="checkmate"),
            make_chess_game(my_color="black", white_result="win", black_result="lose",
                            termination="checkmate"),
            make_chess_game(my_color="white", white_result="stalemate", black_result="stalemate",
                            termination="stalemate"),
            make_chess_game(my_color="black", white_result="stalemate", black_result="stalemate",
                            termination="stalemate"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["total_games"] == 4
        assert stats["wins"] == 1
        assert stats["losses"] == 1
        assert stats["draws"] == 2
        assert stats["win_percent"] == 25.0

    def test_wins_by_color(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="checkmate"),
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="time"),
            make_chess_game(my_color="black", white_result="lose", black_result="win",
                            termination="abandon"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["win_white_percent"] == round(200 / 3, 2)
        assert stats["win_black_percent"] == round(100 / 3, 2)

    def test_termination_percentages(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="checkmate"),
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="time"),
            make_chess_game(my_color="black", white_result="lose", black_result="win",
                            termination="abandon"),
            make_chess_game(my_color="white", white_result="win", black_result="lose",
                            termination="checkmate"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        # 4 wins total: 2 checkmate, 1 time, 1 abandon
        assert stats["checkmate_win_percent"] == 50.0
        assert stats["time_win_percent"] == 25.0
        assert stats["abandon_win_percent"] == 25.0

    def test_clock_stats_are_stubbed(self):
        games = [make_chess_game()]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["avg_my_clock_on_checkmate_sec"] == 0
        assert stats["avg_opp_clock_on_my_time_loss_sec"] == 0

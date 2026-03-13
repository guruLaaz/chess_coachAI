from chessgameanalyzer import ChessGameAnalyzer
from helpers import make_chess_game


class TestSummarize:
    def test_empty_games(self):
        analyzer = ChessGameAnalyzer("player", [])
        assert analyzer.summarize() == {}

    def test_all_wins_as_white(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["total_games"] == 2
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["draws"] == 0
        assert stats["win_percent"] == 100.0

    def test_all_wins_as_black(self):
        games = [
            make_chess_game(my_color="black", white_result="lose", black_result="win"),
            make_chess_game(my_color="black", white_result="lose", black_result="win"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["total_games"] == 2
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["draws"] == 0
        assert stats["win_percent"] == 100.0

    def test_all_losses_as_white(self):
        games = [
            make_chess_game(my_color="white", white_result="lose", black_result="win"),
            make_chess_game(my_color="white", white_result="timeout", black_result="win"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["wins"] == 0
        assert stats["losses"] == 2
        assert stats["win_percent"] == 0.0

    def test_all_losses_as_black(self):
        games = [
            make_chess_game(my_color="black", white_result="win", black_result="checkmated"),
            make_chess_game(my_color="black", white_result="win", black_result="timeout"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["wins"] == 0
        assert stats["losses"] == 2
        assert stats["win_percent"] == 0.0

    def test_mix_of_results_both_colors(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
            make_chess_game(my_color="black", white_result="win", black_result="lose"),
            make_chess_game(my_color="white", white_result="stalemate", black_result="stalemate"),
            make_chess_game(my_color="black", white_result="stalemate", black_result="stalemate"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["total_games"] == 4
        assert stats["wins"] == 1
        assert stats["losses"] == 1
        assert stats["draws"] == 2
        assert stats["win_percent"] == 25.0

    def test_wins_by_color(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
            make_chess_game(my_color="black", white_result="lose", black_result="win"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        # 2 wins out of 2 white games = 100%, 1 win out of 1 black game = 100%
        assert stats["games_white"] == 2
        assert stats["games_black"] == 1
        assert stats["win_white_percent"] == 100.0
        assert stats["win_black_percent"] == 100.0

    def test_win_percent_by_color_mixed(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
            make_chess_game(my_color="white", white_result="lose", black_result="win"),
            make_chess_game(my_color="white", white_result="stalemate", black_result="stalemate"),
            make_chess_game(my_color="black", white_result="win", black_result="checkmated"),
            make_chess_game(my_color="black", white_result="lose", black_result="win"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["games_white"] == 3
        assert stats["games_black"] == 2
        # 1 win / 3 white games = 33.33%
        assert stats["win_white_percent"] == 33.33
        # 1 win / 2 black games = 50%
        assert stats["win_black_percent"] == 50.0

    def test_no_games_as_one_color(self):
        games = [
            make_chess_game(my_color="white", white_result="win", black_result="lose"),
        ]
        stats = ChessGameAnalyzer("player", games).summarize()

        assert stats["games_white"] == 1
        assert stats["games_black"] == 0
        assert stats["win_white_percent"] == 100.0
        assert stats["win_black_percent"] == 0

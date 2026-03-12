"""URL path parser utilities for user routes."""


def parse_user_path(user_path):
    """Parse a URL user path into (chesscom_user, lichess_user).

    "Hikaru"                  -> ("hikaru", None)
    "-/DrNykterstein"         -> (None, "drnykterstein")
    "Hikaru/DrNykterstein"    -> ("hikaru", "drnykterstein")
    """
    parts = user_path.split("/", 1)

    if len(parts) == 1:
        # Single segment: chess.com only
        return (parts[0].lower(), None)

    chesscom_part, lichess_part = parts[0], parts[1]

    if chesscom_part == "-":
        # Dash means no chess.com user
        return (None, lichess_part.lower())

    return (chesscom_part.lower(), lichess_part.lower())


def build_user_path(chesscom_user, lichess_user):
    """Build a URL user path from (chesscom_user, lichess_user).

    ("hikaru", None)              -> "hikaru"
    (None, "drnykterstein")       -> "-/drnykterstein"
    ("hikaru", "drnykterstein")   -> "hikaru/drnykterstein"
    """
    if chesscom_user and lichess_user:
        return f"{chesscom_user.lower()}/{lichess_user.lower()}"
    elif chesscom_user:
        return chesscom_user.lower()
    elif lichess_user:
        return f"-/{lichess_user.lower()}"
    else:
        raise ValueError("At least one username must be provided")

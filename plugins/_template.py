"""Copy this file to plugins/your_engine.py (no underscore) and edit it."""

ENGINE_NAME = "Template"  # shown in the menu, must be unique
ENGINE_AUTHOR = "Your name"  # optional
ENGINE_DESCRIPTION = "Plays the first legal move it finds."  # optional, shown as a tooltip


def choose_Move(board_View, time_Limit_Ms):
    # return a square from board_View.legal_Moves(); 0 is a1, 63 is h8
    return board_View.legal_Moves()[0]

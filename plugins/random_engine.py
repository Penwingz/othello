"""plays a random legal move.This is for testing purposes omly"""

import random

ENGINE_NAME = "Random gambler"
ENGINE_AUTHOR = "adi"
ENGINE_DESCRIPTION = "picks any legal move at random, this is a gamble"


def choose_Move(board_View, time_Limit_Ms):
    return random.choice(board_View.legal_Moves())

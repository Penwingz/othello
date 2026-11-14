"""Greedy engine that goes for corners and avoids the squares next to them."""

ENGINE_NAME = "Corner Hogger" #corner hunting as logic
ENGINE_AUTHOR = "adi"
ENGINE_DESCRIPTION = "grabs corners and avoids position that will give it away;else flips the most discs"

CORNERS = {0, 7, 56, 63} 

NEXT_TO_CORNER = {
    0: {1, 8, 9},
    7: {6, 14, 15},
    56: {48, 49, 57},
    63: {54, 55, 62},
} # to avoid giving the corner to opponent


def choose_Move(board_View, time_Limit_Ms):
    occupied = board_View.my_Discs | board_View.opp_Discs

    def risky(square):
        return any(
            square in neighbours and not occupied >> corner & 1
            for corner, neighbours in NEXT_TO_CORNER.items()
        )

    def value(square):
        if square in CORNERS:
            return 1000
        after = board_View.play_Move(square)  #see from opponent side 
        their_Discs, my_Discs = after.disc_Counts()
        flipped = my_Discs - board_View.disc_Counts()[0] - 1
        return flipped - (500 if risky(square) else 0)

    return max(board_View.legal_Moves(), key=value)

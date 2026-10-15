"""Panel size and place for each state. The sizes are the notch's on a screen without a notch
(`IslandGeometry.swift`): a pill when hidden, ears when peeking, a 520 x 380 panel when open."""

from dataclasses import dataclass

from codebuddy_overlay.island import State

PILL_WIDTH = 80
PILL_HEIGHT = 24
EAR_WIDTH = 76
PREVIEW_WIDTH = 460
PREVIEW_HEIGHT = 30
EXPANDED_WIDTH = 520
EXPANDED_HEIGHT = 380


@dataclass(frozen=True)
class Layout:
    width: int
    height: int
    radius: int  # bottom corners; the top edge is flat against the top of the screen


def layout(state: State, preview: bool = False) -> Layout:
    match state:
        case State.HIDDEN:
            return Layout(PILL_WIDTH, PILL_HEIGHT, 8)
        case State.PEEK if preview:
            return Layout(
                max(PREVIEW_WIDTH, PILL_WIDTH + 2 * EAR_WIDTH), PILL_HEIGHT + PREVIEW_HEIGHT, 14
            )
        case State.PEEK:
            return Layout(PILL_WIDTH + 2 * EAR_WIDTH, PILL_HEIGHT, 10)
        case State.EXPANDED:
            return Layout(EXPANDED_WIDTH, EXPANDED_HEIGHT, 24)


def top_center(screen_x: int, screen_y: int, screen_width: int, size: Layout) -> tuple[int, int]:
    """Top-left corner that centres the panel at the top of the screen's available area."""
    return screen_x + (screen_width - size.width) // 2, screen_y

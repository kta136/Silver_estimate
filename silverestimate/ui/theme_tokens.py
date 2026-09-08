"""Shared color tokens for desktop UI styling."""

PAGE_BG = "#f7f8fa"
SURFACE_BG = "#ffffff"
CARD_BORDER = "#d9dde2"
CARD_BORDER_SOFT = "#e1e4e8"
INPUT_BORDER = "#ccd0d6"
PRIMARY_BG = "#007f89"
PRIMARY_BG_HOVER = "#00939d"
PRIMARY_BG_PRESSED = "#006670"
DANGER_BG = "#fff1f2"
DANGER_BORDER = "#ff9ca4"
SELECTION_BG = "#e0f2f3"
SELECTION_BORDER = "#00848e"
HEADER_BG = "#f6f7f8"
HEADER_TEXT = "#334155"
TEXT_STRONG = "#0f172a"
TEXT_MUTED = "#526176"
FIELD_TEXT = "#475569"
FOCUS_RING = "#007f89"
SUCCESS_BG = "#ecfdf5"
SUCCESS_BORDER = "#bbf7d0"
SUCCESS_TEXT = "#166534"
WARNING_BG = "#fff7ed"
WARNING_BORDER = "#fdba74"
WARNING_TEXT = "#9a3412"
INFO_BG = "#f0f8f8"
INFO_BORDER = "#c1dedf"
INFO_TEXT = "#006d77"
RADIUS_SM = "6px"
RADIUS_MD = "8px"
DENSE_ROW_HEIGHT = 28
DENSE_HEADER_HEIGHT = 30


def apply_theme_tokens(stylesheet: str) -> str:
    """Replace token placeholders in static stylesheet strings."""

    replacements = {
        "__PAGE_BG__": PAGE_BG,
        "__SURFACE_BG__": SURFACE_BG,
        "__CARD_BORDER__": CARD_BORDER,
        "__CARD_BORDER_SOFT__": CARD_BORDER_SOFT,
        "__INPUT_BORDER__": INPUT_BORDER,
        "__PRIMARY_BG__": PRIMARY_BG,
        "__PRIMARY_BG_HOVER__": PRIMARY_BG_HOVER,
        "__PRIMARY_BG_PRESSED__": PRIMARY_BG_PRESSED,
        "__DANGER_BG__": DANGER_BG,
        "__DANGER_BORDER__": DANGER_BORDER,
        "__SELECTION_BG__": SELECTION_BG,
        "__SELECTION_BORDER__": SELECTION_BORDER,
        "__HEADER_BG__": HEADER_BG,
        "__HEADER_TEXT__": HEADER_TEXT,
        "__TEXT_STRONG__": TEXT_STRONG,
        "__TEXT_MUTED__": TEXT_MUTED,
        "__FIELD_TEXT__": FIELD_TEXT,
        "__FOCUS_RING__": FOCUS_RING,
        "__SUCCESS_BG__": SUCCESS_BG,
        "__SUCCESS_BORDER__": SUCCESS_BORDER,
        "__SUCCESS_TEXT__": SUCCESS_TEXT,
        "__WARNING_BG__": WARNING_BG,
        "__WARNING_BORDER__": WARNING_BORDER,
        "__WARNING_TEXT__": WARNING_TEXT,
        "__INFO_BG__": INFO_BG,
        "__INFO_BORDER__": INFO_BORDER,
        "__INFO_TEXT__": INFO_TEXT,
        "__RADIUS_SM__": RADIUS_SM,
        "__RADIUS_MD__": RADIUS_MD,
    }

    for marker, value in replacements.items():
        stylesheet = stylesheet.replace(marker, value)
    return stylesheet

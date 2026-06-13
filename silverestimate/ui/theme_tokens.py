"""Shared color tokens for desktop UI styling."""

PAGE_BG = "#f3f6fb"
SURFACE_BG = "#ffffff"
CARD_BORDER = "#d8e1ec"
CARD_BORDER_SOFT = "#d6dee8"
INPUT_BORDER = "#cbd5e1"
PRIMARY_BG = "#0f766e"
PRIMARY_BG_HOVER = "#0d9488"
PRIMARY_BG_PRESSED = "#0b5f59"
DANGER_BG = "#fff1f2"
DANGER_BORDER = "#fda4af"
SELECTION_BG = "#dbeafe"
SELECTION_BORDER = "#60a5fa"
HEADER_BG = "#f8fafc"
HEADER_TEXT = "#334155"
TEXT_STRONG = "#0f172a"
TEXT_MUTED = "#64748b"
FIELD_TEXT = "#475569"
FOCUS_RING = "#2563eb"
SUCCESS_BG = "#ecfdf5"
SUCCESS_BORDER = "#bbf7d0"
SUCCESS_TEXT = "#166534"
WARNING_BG = "#fff7ed"
WARNING_BORDER = "#fdba74"
WARNING_TEXT = "#9a3412"
INFO_BG = "#eff6ff"
INFO_BORDER = "#bfdbfe"
INFO_TEXT = "#1d4ed8"
RADIUS_SM = "6px"
RADIUS_MD = "8px"
DENSE_ROW_HEIGHT = 26
DENSE_HEADER_HEIGHT = 28


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

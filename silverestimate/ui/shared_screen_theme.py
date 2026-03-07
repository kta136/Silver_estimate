"""Shared QSS helpers for card-based management screens."""

from .theme_tokens import (
    CARD_BORDER,
    DANGER_BG,
    DANGER_BORDER,
    FOCUS_RING,
    HEADER_BG,
    HEADER_TEXT,
    INPUT_BORDER,
    PAGE_BG,
    PRIMARY_BG,
    PRIMARY_BG_HOVER,
    SELECTION_BG,
    SURFACE_BG,
    TEXT_MUTED,
    TEXT_STRONG,
    FIELD_TEXT,
)


def build_management_screen_stylesheet(
    *,
    root_selector: str,
    card_names: list[str],
    title_label: str,
    subtitle_label: str,
    field_label: str | None = None,
    primary_button: str | None = None,
    secondary_button: str | None = None,
    danger_button: str | None = None,
    input_selectors: list[str] | None = None,
    include_table: bool = False,
    extra_rules: str = "",
) -> str:
    """Build a consistent stylesheet for secondary management screens."""

    rules: list[str] = [
        f"""
        {root_selector} {{
            background-color: {PAGE_BG};
        }}
        """,
    ]

    if card_names:
        card_selector = ",\n".join(f"QFrame#{name}" for name in card_names)
        rules.append(
            f"""
            {card_selector} {{
                background-color: {SURFACE_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}
            """
        )

    rules.append(
        f"""
        QLabel#{title_label} {{
            color: {TEXT_STRONG};
            font-size: 16pt;
            font-weight: 700;
        }}
        QLabel#{subtitle_label} {{
            color: {TEXT_MUTED};
            font-size: 9pt;
        }}
        """
    )

    if field_label:
        rules.append(
            f"""
            QLabel#{field_label} {{
                color: {FIELD_TEXT};
                font-size: 8.5pt;
                font-weight: 600;
            }}
            """
        )

    button_selectors = [
        f"QPushButton#{name}"
        for name in (primary_button, secondary_button, danger_button)
        if name
    ]
    if button_selectors:
        rules.append(
            f"""
            {",\n".join(button_selectors)} {{
                border-radius: 8px;
                padding: 5px 10px;
                min-height: 20px;
                font-weight: 600;
            }}
            """
        )

    if primary_button:
        rules.append(
            f"""
            QPushButton#{primary_button} {{
                color: #ffffff;
                background-color: {PRIMARY_BG};
                border: 1px solid {PRIMARY_BG};
            }}
            QPushButton#{primary_button}:hover {{
                background-color: {PRIMARY_BG_HOVER};
                border-color: {PRIMARY_BG_HOVER};
            }}
            """
        )

    if secondary_button:
        rules.append(
            f"""
            QPushButton#{secondary_button} {{
                color: {TEXT_STRONG};
                background-color: {HEADER_BG};
                border: 1px solid {INPUT_BORDER};
            }}
            QPushButton#{secondary_button}:hover {{
                background-color: #eef2f7;
                border-color: #94a3b8;
            }}
            """
        )

    if danger_button:
        rules.append(
            f"""
            QPushButton#{danger_button} {{
                color: #b91c1c;
                background-color: {DANGER_BG};
                border: 1px solid {DANGER_BORDER};
            }}
            QPushButton#{danger_button}:hover {{
                background-color: #ffe4e6;
                border-color: #fb7185;
            }}
            """
        )

    if input_selectors:
        input_selector = ",\n".join(input_selectors)
        rules.append(
            f"""
            {input_selector} {{
                background-color: {SURFACE_BG};
                border: 1px solid {INPUT_BORDER};
                border-radius: 8px;
                padding: 4px 8px;
                min-height: 18px;
            }}
            {input_selector}:focus {{
                border: 2px solid {FOCUS_RING};
            }}
            """
        )

    if include_table:
        rules.append(
            """
            QTableView {
                background-color: """
            + SURFACE_BG
            + """;
                border: 1px solid #d6dee8;
                border-radius: 12px;
                gridline-color: #d9e2ec;
                selection-background-color: """
            + SELECTION_BG
            + """;
                selection-color: """
            + TEXT_STRONG
            + """;
            }
            QHeaderView::section {
                background-color: """
            + HEADER_BG
            + """;
                color: """
            + HEADER_TEXT
            + """;
                border: none;
                border-right: 1px solid #e2e8f0;
                border-bottom: 1px solid #e2e8f0;
                padding: 6px 8px;
                font-weight: 700;
            }
            """
        )

    if extra_rules.strip():
        rules.append(extra_rules.strip())

    return "\n".join(rule.strip() for rule in rules if rule.strip())

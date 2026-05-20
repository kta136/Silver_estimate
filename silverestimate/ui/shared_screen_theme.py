"""Shared QSS helpers for card-based management screens."""

from .theme_tokens import (
    CARD_BORDER,
    CARD_BORDER_SOFT,
    DANGER_BG,
    DANGER_BORDER,
    FIELD_TEXT,
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
    apply_theme_tokens,
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
            color: {TEXT_STRONG};
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
                color: {TEXT_STRONG};
            }}
            """
        )

    rules.append(
        f"""
        QLabel {{
            color: {TEXT_STRONG};
        }}
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
                color: {TEXT_STRONG};
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
                color: {FIELD_TEXT};
                padding: 4px 8px;
                min-height: 18px;
                selection-background-color: {SELECTION_BG};
                selection-color: {TEXT_STRONG};
            }}
            {input_selector}:focus {{
                border: 2px solid {FOCUS_RING};
            }}
            {input_selector}:disabled {{
                background-color: {HEADER_BG};
                border-color: {CARD_BORDER_SOFT};
                color: {TEXT_MUTED};
            }}
            {input_selector}:read-only {{
                background-color: {HEADER_BG};
                border-color: {CARD_BORDER_SOFT};
                color: {FIELD_TEXT};
            }}
            QComboBox {{
                padding-right: 34px;
            }}
            QComboBox::drop-down {{
                background-color: {HEADER_BG};
                border-left: 1px solid {INPUT_BORDER};
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 30px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {SURFACE_BG};
                border: 1px solid {INPUT_BORDER};
                color: {TEXT_STRONG};
                selection-background-color: {SELECTION_BG};
                selection-color: {TEXT_STRONG};
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 24px;
                padding: 4px 8px;
            }}
            QComboBox QAbstractItemView::item:selected,
            QComboBox QAbstractItemView::item:selected:!active {{
                background-color: {SELECTION_BG};
                color: {TEXT_STRONG};
            }}
            QSpinBox,
            QDoubleSpinBox,
            QDateEdit,
            QTimeEdit,
            QDateTimeEdit {{
                padding-right: 30px;
            }}
            QSpinBox::up-button,
            QDoubleSpinBox::up-button,
            QDateEdit::up-button,
            QTimeEdit::up-button,
            QDateTimeEdit::up-button {{
                background-color: {HEADER_BG};
                border-left: 1px solid {INPUT_BORDER};
                border-top-right-radius: 8px;
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 26px;
            }}
            QSpinBox::down-button,
            QDoubleSpinBox::down-button,
            QDateEdit::down-button,
            QTimeEdit::down-button,
            QDateTimeEdit::down-button {{
                background-color: {HEADER_BG};
                border-left: 1px solid {INPUT_BORDER};
                border-bottom-right-radius: 8px;
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 26px;
            }}
            """
        )

    rules.append(
        f"""
        QGroupBox {{
            background-color: {SURFACE_BG};
            border: 1px solid {CARD_BORDER};
            border-radius: 10px;
            color: {TEXT_STRONG};
            font-weight: 700;
            margin-top: 12px;
            padding: 12px 12px 10px 12px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
        }}
        QCheckBox,
        QRadioButton {{
            color: {TEXT_STRONG};
            spacing: 8px;
        }}
        QCheckBox:disabled,
        QRadioButton:disabled {{
            color: {TEXT_MUTED};
        }}
        QCheckBox::indicator,
        QRadioButton::indicator {{
            background-color: {SURFACE_BG};
            border: 1px solid {INPUT_BORDER};
            height: 14px;
            width: 14px;
        }}
        QCheckBox::indicator {{
            border-radius: 4px;
        }}
        QRadioButton::indicator {{
            border-radius: 7px;
        }}
        QCheckBox::indicator:checked,
        QRadioButton::indicator:checked {{
            background-color: {PRIMARY_BG};
            border-color: {PRIMARY_BG};
        }}
        QMenu {{
            background-color: {SURFACE_BG};
            border: 1px solid {CARD_BORDER};
            color: {TEXT_STRONG};
            padding: 4px;
        }}
        QMenu::item {{
            background-color: transparent;
            color: {TEXT_STRONG};
            padding: 6px 24px 6px 18px;
        }}
        QMenu::item:selected,
        QMenu::item:pressed {{
            background-color: {SELECTION_BG};
            color: {TEXT_STRONG};
        }}
        QMenu::item:disabled {{
            color: {TEXT_MUTED};
        }}
        QMenu::separator {{
            background-color: {CARD_BORDER_SOFT};
            height: 1px;
            margin: 4px 8px;
        }}
        QToolTip {{
            background-color: {SURFACE_BG};
            border: 1px solid {CARD_BORDER};
            border-radius: 4px;
            color: {TEXT_STRONG};
            padding: 4px 6px;
        }}
        QDialogButtonBox QPushButton {{
            background-color: {HEADER_BG};
            border: 1px solid {INPUT_BORDER};
            border-radius: 8px;
            color: {TEXT_STRONG};
            font-weight: 600;
            min-height: 24px;
            min-width: 78px;
            padding: 5px 12px;
        }}
        QDialogButtonBox QPushButton:hover {{
            background-color: {SELECTION_BG};
            border-color: {HEADER_TEXT};
        }}
        QDialogButtonBox QPushButton:disabled {{
            background-color: {CARD_BORDER_SOFT};
            border-color: {CARD_BORDER};
            color: {TEXT_MUTED};
        }}
        QCalendarWidget {{
            background-color: {SURFACE_BG};
            border: 1px solid {CARD_BORDER};
            color: {TEXT_STRONG};
        }}
        QCalendarWidget QWidget {{
            background-color: {SURFACE_BG};
            color: {TEXT_STRONG};
        }}
        QCalendarWidget QToolButton {{
            background-color: {HEADER_BG};
            border: 1px solid {INPUT_BORDER};
            border-radius: 6px;
            color: {TEXT_STRONG};
            margin: 2px;
            padding: 4px 8px;
        }}
        QCalendarWidget QToolButton:hover {{
            background-color: {SELECTION_BG};
            border-color: {FOCUS_RING};
        }}
        QScrollArea,
        QStackedWidget {{
            background-color: transparent;
            color: {TEXT_STRONG};
        }}
        QScrollBar:vertical,
        QScrollBar:horizontal {{
            background-color: {HEADER_BG};
            border: none;
            margin: 0;
        }}
        QScrollBar:vertical {{
            width: 12px;
        }}
        QScrollBar:horizontal {{
            height: 12px;
        }}
        QScrollBar::handle:vertical,
        QScrollBar::handle:horizontal {{
            background-color: {INPUT_BORDER};
            border-radius: 6px;
            min-height: 24px;
            min-width: 24px;
        }}
        QScrollBar::handle:vertical:hover,
        QScrollBar::handle:horizontal:hover {{
            background-color: {TEXT_MUTED};
        }}
        QScrollBar::add-line,
        QScrollBar::sub-line,
        QScrollBar::add-page,
        QScrollBar::sub-page {{
            background: transparent;
            border: none;
        }}
        """
    )

    if include_table:
        rules.append(
            f"""
            QTableView {{
                background-color: {SURFACE_BG};
                border: 1px solid {CARD_BORDER_SOFT};
                border-radius: 12px;
                gridline-color: {CARD_BORDER};
                selection-background-color: {SELECTION_BG};
                selection-color: {TEXT_STRONG};
            }}
            QHeaderView::section {{
                background-color: {HEADER_BG};
                color: {HEADER_TEXT};
                border: none;
                border-right: 1px solid {CARD_BORDER_SOFT};
                border-bottom: 1px solid {CARD_BORDER_SOFT};
                padding: 6px 8px;
                font-weight: 700;
            }}
            """
        )

    if extra_rules.strip():
        rules.append(apply_theme_tokens(extra_rules.strip()))

    return "\n".join(rule.strip() for rule in rules if rule.strip())

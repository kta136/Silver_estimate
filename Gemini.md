# Project Learnings (Silver Estimate)

This file documents key learnings, decisions, and important information about the Silver Estimate project.
## Currency Formatting (April 24, 2025)

- **File:** `print_manager.py`
- **Change:** Corrected the `format_indian_rupees` function to properly implement comma separation according to the Indian numbering system (lakhs, crores). The previous implementation incorrectly used thousand separators.
- **Location:** The function is used to format the final Silver Cost and Total Cost on the printed estimate slip.
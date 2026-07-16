from silverestimate.infrastructure.paths import get_database_path

APP_NAME = "Silver Estimation App"
APP_VERSION = "3.03"
APP_TITLE = f"{APP_NAME} v{APP_VERSION}"

# Keep a stable organization identifier for all new installs.
SETTINGS_ORG = "SilverEstimate"
# Legacy org used only by the one-time settings migration.
LEGACY_SETTINGS_ORG = "YourCompany"
SETTINGS_APP = "SilverEstimateApp"

# Default paths
DB_PATH = str(get_database_path())
LOG_DIR = "logs"

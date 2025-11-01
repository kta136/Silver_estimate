"""Custom exception hierarchy for Silver Estimation App.

This module defines a structured exception hierarchy for better error handling
and debugging throughout the application.
"""


class SilverEstimateError(Exception):
    """Base exception for all Silver Estimation App errors."""

    pass


# Database-related exceptions
class DatabaseError(SilverEstimateError):
    """Base exception for database-related errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    pass


class DatabaseEncryptionError(DatabaseError):
    """Raised when database encryption/decryption fails."""

    pass


class DatabaseMigrationError(DatabaseError):
    """Raised when database migration fails."""

    pass


class DatabaseIntegrityError(DatabaseError):
    """Raised when database integrity constraint is violated."""

    pass


# Security-related exceptions
class SecurityError(SilverEstimateError):
    """Base exception for security-related errors."""

    pass


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""

    pass


class EncryptionError(SecurityError):
    """Raised when encryption/decryption operation fails."""

    pass


class CredentialStoreError(SecurityError):
    """Raised when credential storage/retrieval fails."""

    pass


class InvalidPasswordError(SecurityError):
    """Raised when password validation fails."""

    pass


# Validation-related exceptions
class ValidationError(SilverEstimateError):
    """Base exception for validation errors."""

    pass


class ItemValidationError(ValidationError):
    """Raised when item data validation fails."""

    pass


class EstimateValidationError(ValidationError):
    """Raised when estimate data validation fails."""

    pass


class SilverBarValidationError(ValidationError):
    """Raised when silver bar data validation fails."""

    pass


# Business logic exceptions
class BusinessLogicError(SilverEstimateError):
    """Base exception for business logic violations."""

    pass


class CalculationError(BusinessLogicError):
    """Raised when calculation fails or produces invalid results."""

    pass


class InsufficientInventoryError(BusinessLogicError):
    """Raised when operation requires more inventory than available."""

    pass


class DuplicateRecordError(BusinessLogicError):
    """Raised when attempting to create a duplicate record."""

    pass


# Import/Export exceptions
class ImportExportError(SilverEstimateError):
    """Base exception for import/export operations."""

    pass


class FileFormatError(ImportExportError):
    """Raised when file format is invalid or unsupported."""

    pass


class DataMappingError(ImportExportError):
    """Raised when data mapping fails during import/export."""

    pass


# Configuration exceptions
class ConfigurationError(SilverEstimateError):
    """Base exception for configuration-related errors."""

    pass


class SettingsError(ConfigurationError):
    """Raised when settings operation fails."""

    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""

    pass


# Network/Service exceptions
class ServiceError(SilverEstimateError):
    """Base exception for external service errors."""

    pass


class LiveRateServiceError(ServiceError):
    """Raised when live rate fetching fails."""

    pass


class NetworkError(ServiceError):
    """Raised when network operation fails."""

    pass


class ServiceUnavailableError(ServiceError):
    """Raised when required service is unavailable."""

    pass

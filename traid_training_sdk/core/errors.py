class SdkError(Exception):
    """Base SDK error."""


class ConfigurationError(SdkError):
    pass


class DataSourceError(SdkError):
    pass


class TrainingError(SdkError):
    pass


class EvaluationError(SdkError):
    pass


class RegistryError(SdkError):
    pass


class RunLifecycleError(SdkError):
    pass


class IOErrorSDK(SdkError):
    pass


class NotImplementedSDK(SdkError):
    pass


class NotAvailableSDK(SdkError):
    """Raised when an optional dependency or integration is unavailable."""
    pass

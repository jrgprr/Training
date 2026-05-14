from importlib import import_module

__all__ = [
    "GarminImportRequest",
    "ImportFetchMetadata",
    "ImportJobBreakdown",
    "NormalizedActivity",
    "NormalizedDailyMetric",
    "GarminConnectAdapter",
    "GarminConnectConfiguration",
    "GarminConnectImportError",
    "GarminConnectNotConfiguredError",
    "GarminImportPipeline",
    "GarminImportPreview",
    "GarminImportStorage",
    "ImportJobSummary",
]

_EXPORT_MAP = {
    "GarminImportRequest": (".contracts", "GarminImportRequest"),
    "ImportFetchMetadata": (".contracts", "ImportFetchMetadata"),
    "ImportJobBreakdown": (".contracts", "ImportJobBreakdown"),
    "NormalizedActivity": (".contracts", "NormalizedActivity"),
    "NormalizedDailyMetric": (".contracts", "NormalizedDailyMetric"),
    "GarminConnectAdapter": (".garmin_connect", "GarminConnectAdapter"),
    "GarminConnectConfiguration": (".garmin_connect", "GarminConnectConfiguration"),
    "GarminConnectImportError": (".garmin_connect", "GarminConnectImportError"),
    "GarminConnectNotConfiguredError": (".garmin_connect", "GarminConnectNotConfiguredError"),
    "GarminImportPipeline": (".pipeline", "GarminImportPipeline"),
    "GarminImportPreview": (".pipeline", "GarminImportPreview"),
    "GarminImportStorage": (".storage", "GarminImportStorage"),
    "ImportJobSummary": (".storage", "ImportJobSummary"),
}


def __getattr__(name: str):
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORT_MAP[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value

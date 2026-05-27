from importlib import import_module

__all__ = [
    "GarminImportRequest",
    "ImportFetchMetadata",
    "ImportJobBreakdown",
    "NormalizedActivity",
    "NormalizedDailyMetric",
    "NormalizedMetricReading",
    "NormalizedSegmentDefinition",
    "NormalizedSegmentEffort",
    "GarminConnectAdapter",
    "GarminConnectConfiguration",
    "GarminConnectAuthenticationImportError",
    "GarminConnectImportError",
    "GarminConnectNotConfiguredError",
    "GarminConnectTransportImportError",
    "classify_garmin_failure",
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
    "NormalizedMetricReading": (".contracts", "NormalizedMetricReading"),
    "NormalizedSegmentDefinition": (".contracts", "NormalizedSegmentDefinition"),
    "NormalizedSegmentEffort": (".contracts", "NormalizedSegmentEffort"),
    "GarminConnectAdapter": (".garmin_connect", "GarminConnectAdapter"),
    "GarminConnectConfiguration": (".garmin_connect", "GarminConnectConfiguration"),
    "GarminConnectAuthenticationImportError": (".garmin_connect", "GarminConnectAuthenticationImportError"),
    "GarminConnectImportError": (".garmin_connect", "GarminConnectImportError"),
    "GarminConnectNotConfiguredError": (".garmin_connect", "GarminConnectNotConfiguredError"),
    "GarminConnectTransportImportError": (".garmin_connect", "GarminConnectTransportImportError"),
    "classify_garmin_failure": (".garmin_connect", "classify_garmin_failure"),
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

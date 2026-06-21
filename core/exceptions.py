class SubtiLearnException(Exception):
    """Excepción base para la app"""
    pass

class InvalidDraftError(SubtiLearnException):
    """Draft JSON no válido"""
    pass

class BackupError(SubtiLearnException):
    """Falla al crear backup"""
    pass

class AnalysisError(SubtiLearnException):
    """Falla en análisis"""
    pass
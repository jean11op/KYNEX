class ErrorPersistencia(Exception):
    """No se pudo acceder, leer o escribir en el almacenamiento."""


class ErrorDatosPersistidos(ErrorPersistencia):
    """La información guardada está incompleta o es inválida."""

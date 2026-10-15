# Un dato incumple una regla del sistema.
# Crear un perfil con el nombre vacío.
class ErrorDominio(ValueError):
    """La solicitud no cumple una regla del negocio."""

# No existe el elemento solicitado.
# Seleccionar un perfil que fue eliminado.
class ErrorNoEncontrado(ErrorDominio):
    pass

# La operación entra en conflicto o necesita confirmación.
# Por ejemplo al crear un perfil con un nombre que ya existe.
class ErrorConflicto(ErrorDominio):
    pass

# No se puede realizar una operación de control.
class ErrorControl(ErrorDominio):
    pass

import math
from holocontrol.domain.errores import ErrorDominio

def validar_texto(valor: str, campo: str, maximo: int = 100) -> str:
    if not isinstance(valor, str) or not valor.strip() or len(valor.strip()) > maximo:
        raise ErrorDominio(f"{campo}: indique entre 1 y {maximo} caracteres.")
    return valor.strip()


def validar_numero(valor: float, campo: str, minimo: float, maximo: float) -> None:
    if (isinstance(valor, bool) or not isinstance(valor, (int, float))
            or not math.isfinite(valor) or not minimo <= valor <= maximo):
        raise ErrorDominio(f"{campo}: debe estar entre {minimo} y {maximo}.")


def validar_entero(valor: int, campo: str, minimo: int, maximo: int) -> None:
    if type(valor) is not int:
        raise ErrorDominio(f"{campo}: se requiere un entero.")
    validar_numero(valor, campo, minimo, maximo)

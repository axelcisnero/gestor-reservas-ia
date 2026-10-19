"""HU-1: pago SIMULADO de reservas con opción de guardar los datos.

No hay pasarela real (proyecto académico). Reglas de seguridad aplicadas:
- El número completo y el CVV solo se usan para validar y nunca se guardan ni se registran.
- Del método guardado solo se conserva titular, marca, últimos 4 dígitos y vencimiento.
"""
import re
import uuid
from decimal import Decimal

from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import PaymentProfile


class PagoError(Exception):
    """Error de pago (mensaje apto para mostrar al usuario)."""


def luhn_valido(numero: str) -> bool:
    if not numero.isdigit() or not 13 <= len(numero) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(numero)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def detectar_marca(numero: str) -> str:
    if numero.startswith("4"):
        return "Visa"
    if re.match(r"^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))", numero):
        return "Mastercard"
    if re.match(r"^3[47]", numero):
        return "Amex"
    return "Tarjeta"


MAX_TITULAR = 100


def _texto(valor):
    """Solo acepta texto o números; cualquier otro tipo (listas, objetos) es inválido."""
    if valor is None:
        return ""
    if isinstance(valor, bool) or not isinstance(valor, (str, int)):
        raise PagoError("Datos de pago inválidos.")
    return str(valor).strip()


@sensitive_variables("numero", "cvv")
def validar_tarjeta(numero, titular, mes, anio, cvv):
    """Valida los datos del formulario y devuelve solo lo que se puede guardar."""
    numero = re.sub(r"[\s-]", "", _texto(numero))
    if titular is not None and not isinstance(titular, str):
        raise PagoError("Datos de pago inválidos.")
    titular = _texto(titular)
    cvv = _texto(cvv)
    if not titular:
        raise PagoError("Ingresa el nombre del titular.")
    if len(titular) > MAX_TITULAR:
        raise PagoError(f"El nombre del titular no puede superar {MAX_TITULAR} caracteres.")
    if not luhn_valido(numero):
        raise PagoError("El número de tarjeta no es válido.")
    try:
        mes, anio = int(_texto(mes)), int(_texto(anio))
    except (TypeError, ValueError):
        raise PagoError("Fecha de vencimiento inválida.")
    if anio < 100:
        anio += 2000
    if not 1 <= mes <= 12:
        raise PagoError("Fecha de vencimiento inválida.")
    hoy = timezone.localdate()
    if (anio, mes) < (hoy.year, hoy.month):
        raise PagoError("La tarjeta está vencida.")
    marca = detectar_marca(numero)
    largo_cvv = 4 if marca == "Amex" else 3
    if not (cvv.isdigit() and len(cvv) == largo_cvv):
        raise PagoError(f"El CVV debe tener {largo_cvv} dígitos.")
    return {"holder_name": titular, "brand": marca, "last4": numero[-4:], "exp_month": mes, "exp_year": anio}


def perfil_vigente(user):
    perfil = PaymentProfile.objects.filter(user=user).first()
    if perfil is None:
        return None
    hoy = timezone.localdate()
    if (perfil.exp_year, perfil.exp_month) < (hoy.year, hoy.month):
        return None
    return perfil


@sensitive_variables("pago", "datos")
def cobrar(user, monto: Decimal, pago: dict | None) -> str:
    """Cobra el monto (simulado) y devuelve la referencia del pago.

    pago = {"modo": "guardado"}  o
    pago = {"modo": "tarjeta", "numero", "titular", "mes", "anio", "cvv", "guardar": bool}
    """
    if not isinstance(pago, dict):
        raise PagoError("Falta la información de pago.")
    modo = pago.get("modo")
    if modo == "guardado":
        if perfil_vigente(user) is None:
            raise PagoError("No tienes un método de pago guardado vigente.")
    elif modo == "tarjeta":
        datos = validar_tarjeta(pago.get("numero"), pago.get("titular"), pago.get("mes"), pago.get("anio"), pago.get("cvv"))
        if pago.get("guardar"):
            PaymentProfile.objects.update_or_create(user=user, defaults=datos)
    else:
        raise PagoError("Modo de pago no reconocido.")
    # Pasarela simulada: siempre aprueba y devuelve una referencia.
    return f"SIM-{uuid.uuid4().hex[:12].upper()}"

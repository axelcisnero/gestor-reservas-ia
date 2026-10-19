"""Lógica de negocio de reservas, separada de las vistas para poder probarla."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import Availability, Booking, Resource
from .pagos import PagoError, cobrar

MAX_SEMANAS_REPETICION = 52


class ReservaError(Exception):
    """Error de validación de una reserva (se muestra tal cual al usuario)."""


def _franjas(inicio, fin, repeat_weeks):
    return [(inicio + timedelta(weeks=i), fin + timedelta(weeks=i)) for i in range(repeat_weeks + 1)]


def validar_franja(resource, inicio, fin, semana=None):
    """Lanza ReservaError si la franja choca con una reserva o un bloqueo."""
    sufijo = f" (semana {semana}: {timezone.localtime(inicio):%d/%m/%Y %H:%M})" if semana else ""
    if Availability.objects.filter(resource=resource, start_time__lt=fin, end_time__gt=inicio).exists():
        raise ReservaError(f"La franja está bloqueada por el administrador{sufijo}.")
    if Booking.objects.filter(resource=resource, start_time__lt=fin, end_time__gt=inicio).exists():
        raise ReservaError(f"Conflicto: ya existe una reserva en esa franja{sufijo}.")


def monto_por_reserva(resource, inicio, fin):
    """HU-1: precio por hora × horas, redondeado a centavos."""
    horas = Decimal((fin - inicio).total_seconds()) / Decimal(3600)
    return (resource.price_per_hour * horas).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def crear_reservas(user, resource_id, inicio, fin, repeat_weeks=0, pago=None):
    """Crea una reserva (y sus repeticiones semanales) de forma atómica: todas o ninguna."""
    if inicio is None or fin is None:
        raise ReservaError("Fecha u hora inválida.")
    # Fechas sin zona horaria se interpretan en la zona del sistema (America/Panama).
    if timezone.is_naive(inicio):
        inicio = timezone.make_aware(inicio)
    if timezone.is_naive(fin):
        fin = timezone.make_aware(fin)
    if fin <= inicio:
        raise ReservaError("La hora de fin debe ser posterior a la de inicio.")
    if inicio < timezone.now():
        raise ReservaError("No se puede reservar en el pasado.")
    if not 0 <= repeat_weeks <= MAX_SEMANAS_REPETICION:
        raise ReservaError(f"Las repeticiones deben estar entre 0 y {MAX_SEMANAS_REPETICION} semanas.")

    with transaction.atomic():
        # En PostgreSQL/MySQL bloquea la fila del recurso para serializar reservas simultáneas.
        # Limitación conocida: SQLite ignora select_for_update (ver AI_LOG.md).
        try:
            resource = Resource.objects.select_for_update().get(pk=resource_id)
        except (Resource.DoesNotExist, ValueError, TypeError):
            raise ReservaError("El recurso no existe.")
        franjas = _franjas(inicio, fin, repeat_weeks)
        # 1) validar TODAS las semanas antes de guardar nada
        for i, (ini, f) in enumerate(franjas, start=1):
            validar_franja(resource, ini, f, semana=i if repeat_weeks else None)
        # 2) cobrar (HU-1); si el pago falla no se guarda nada
        monto = monto_por_reserva(resource, inicio, fin)
        referencia = ""
        if monto > 0:
            try:
                referencia = cobrar(user, monto * len(franjas), pago)
            except PagoError as e:
                raise ReservaError(str(e))
        # 3) guardar todas
        return [
            Booking.objects.create(user=user, resource=resource, start_time=ini, end_time=f,
                                   amount=monto, payment_ref=referencia)
            for ini, f in franjas
        ]

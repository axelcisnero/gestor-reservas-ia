"""Lógica de negocio de reservas, separada de las vistas para poder probarla."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Availability, Booking, Resource

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


def crear_reservas(user, resource_id, inicio, fin, repeat_weeks=0, **extra):
    """Crea una reserva (y sus repeticiones semanales) de forma atómica: todas o ninguna."""
    if inicio is None or fin is None:
        raise ReservaError("Fecha u hora inválida.")
    if fin <= inicio:
        raise ReservaError("La hora de fin debe ser posterior a la de inicio.")
    if inicio < timezone.now():
        raise ReservaError("No se puede reservar en el pasado.")
    if not 0 <= repeat_weeks <= MAX_SEMANAS_REPETICION:
        raise ReservaError(f"Las repeticiones deben estar entre 0 y {MAX_SEMANAS_REPETICION} semanas.")

    with transaction.atomic():
        # Bloquea la fila del recurso para que dos peticiones simultáneas no reserven lo mismo.
        try:
            resource = Resource.objects.select_for_update().get(pk=resource_id)
        except (Resource.DoesNotExist, ValueError, TypeError):
            raise ReservaError("El recurso no existe.")
        franjas = _franjas(inicio, fin, repeat_weeks)
        # 1) validar TODAS las semanas antes de guardar nada
        for i, (ini, f) in enumerate(franjas, start=1):
            validar_franja(resource, ini, f, semana=i if repeat_weeks else None)
        # 2) guardar todas
        return [
            Booking.objects.create(user=user, resource=resource, start_time=ini, end_time=f, **extra)
            for ini, f in franjas
        ]

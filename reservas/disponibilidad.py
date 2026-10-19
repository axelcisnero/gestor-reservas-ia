"""HU-2: cálculo de disponibilidad por día (libre / parcial / completo / bloqueado / pasado)."""
from datetime import datetime, time, timedelta

from django.utils import timezone

from .models import Availability, Booking

HORA_APERTURA = time(9, 0)
HORA_CIERRE = time(21, 0)
MAX_DIAS = 62

COLORES = {
    "libre": "#bbf7d0",      # verde claro
    "parcial": "#fde68a",    # amarillo
    "completo": "#fca5a5",   # rojo claro
    "bloqueado": "#9ca3af",  # gris
    "pasado": "#e5e7eb",     # gris claro
}


def _union_minutos(intervalos, ini, fin):
    """Minutos cubiertos por la unión de intervalos, recortados a [ini, fin)."""
    recortados = sorted((max(a, ini), min(b, fin)) for a, b in intervalos if a < fin and b > ini)
    total, actual_ini, actual_fin = 0, None, None
    for a, b in recortados:
        if actual_fin is None or a > actual_fin:
            if actual_fin is not None:
                total += (actual_fin - actual_ini).total_seconds()
            actual_ini, actual_fin = a, b
        else:
            actual_fin = max(actual_fin, b)
    if actual_fin is not None:
        total += (actual_fin - actual_ini).total_seconds()
    return int(total // 60)


def disponibilidad_por_dia(resource, desde, hasta):
    """Lista de días en [desde, hasta) con su estado. `desde`/`hasta` son date."""
    if (hasta - desde).days > MAX_DIAS:
        hasta = desde + timedelta(days=MAX_DIAS)
    tz = timezone.get_current_timezone()
    rango_ini = timezone.make_aware(datetime.combine(desde, HORA_APERTURA), tz)
    rango_fin = timezone.make_aware(datetime.combine(hasta, HORA_CIERRE), tz)
    reservas = list(Booking.objects.filter(resource=resource, start_time__lt=rango_fin, end_time__gt=rango_ini)
                    .values_list("start_time", "end_time"))
    bloqueos = list(Availability.objects.filter(resource=resource, start_time__lt=rango_fin, end_time__gt=rango_ini)
                    .values_list("start_time", "end_time"))
    hoy = timezone.localdate()
    dias = []
    dia = desde
    while dia < hasta:
        ini = timezone.make_aware(datetime.combine(dia, HORA_APERTURA), tz)
        fin = timezone.make_aware(datetime.combine(dia, HORA_CIERRE), tz)
        total = int((fin - ini).total_seconds() // 60)
        min_bloqueados = _union_minutos(bloqueos, ini, fin)
        min_ocupados = _union_minutos(reservas + bloqueos, ini, fin)
        if dia < hoy:
            estado = "pasado"
        elif min_bloqueados >= total:
            estado = "bloqueado"
        elif min_ocupados >= total:
            estado = "completo"
        elif min_ocupados > 0:
            estado = "parcial"
        else:
            estado = "libre"
        dias.append({
            "fecha": dia.isoformat(),
            "estado": estado,
            "horas_libres": round((total - min_ocupados) / 60, 2),
            "horas_ocupadas": round(min_ocupados / 60, 2),
        })
        dia += timedelta(days=1)
    return dias

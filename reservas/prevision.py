"""HU-3: previsión de demanda por recurso a partir del histórico de reservas.

Método explicable y sin dependencias: regresión lineal por mínimos cuadrados sobre
las horas reservadas por semana. La capacidad semanal es 12 h × 7 días = 84 h.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import Booking

SEMANAS_HISTORICO = 12
SEMANAS_PREVISION = 4
CAPACIDAD_SEMANAL_HORAS = 12 * 7
UMBRAL_ALTO = 0.75
UMBRAL_BAJO = 0.30
AJUSTE_PRECIO = Decimal("0.10")


def inicio_semana(fecha):
    return fecha - timedelta(days=fecha.weekday())  # lunes


def horas_por_semana(resource, semanas=SEMANAS_HISTORICO, hoy=None):
    """Horas reservadas en cada una de las últimas `semanas` semanas completas (lunes a domingo).

    Una reserva que cruza de una semana a otra reparte sus horas entre ambas.
    Cada semana se limita a la capacidad (84 h) por si hay datos fuera del horario.
    """
    hoy = hoy or timezone.localdate()
    lunes_actual = inicio_semana(hoy)
    lunes = [lunes_actual - timedelta(weeks=semanas - i) for i in range(semanas)]
    limites = [timezone.make_aware(datetime.combine(l, time.min)) for l in lunes]
    limites.append(timezone.make_aware(datetime.combine(lunes_actual, time.min)))
    horas = [0.0] * semanas
    for ini, fin in Booking.objects.filter(resource=resource, start_time__lt=limites[-1], end_time__gt=limites[0]) \
            .values_list("start_time", "end_time"):
        for i in range(semanas):
            a, b = max(ini, limites[i]), min(fin, limites[i + 1])
            if a < b:
                horas[i] += (b - a).total_seconds() / 3600
    return lunes, [round(min(h, CAPACIDAD_SEMANAL_HORAS), 1) for h in horas]


def regresion_lineal(valores):
    """Devuelve (intercepto, pendiente) por mínimos cuadrados con x = 0..n-1."""
    n = len(valores)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return float(valores[0]), 0.0
    xs = range(n)
    mx, my = (n - 1) / 2, sum(valores) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, valores))
    pendiente = sxy / sxx
    return my - pendiente * mx, pendiente


def pronosticar(valores, semanas=SEMANAS_PREVISION):
    a, b = regresion_lineal(valores)
    n = len(valores)
    # La demanda no puede ser negativa ni superar la capacidad.
    return [round(min(max(a + b * (n + i), 0.0), CAPACIDAD_SEMANAL_HORAS), 1) for i in range(semanas)]


def sugerencia(ocupacion, precio):
    """Sugerencia de precio e inventario según la ocupación prevista (0..1)."""
    q = Decimal("0.01")
    if ocupacion >= UMBRAL_ALTO:
        nuevo = (precio * (1 + AJUSTE_PRECIO)).quantize(q, ROUND_HALF_UP)
        texto = "Demanda alta: subir el precio un 10 %"
        if ocupacion >= 0.9:
            texto += " y evaluar habilitar otro recurso"
        return {"accion": "subir", "texto": texto, "precio_sugerido": nuevo}
    if ocupacion <= UMBRAL_BAJO:
        nuevo = (precio * (1 - AJUSTE_PRECIO)).quantize(q, ROUND_HALF_UP)
        return {"accion": "bajar", "texto": "Demanda baja: bajar el precio un 10 % o crear promociones",
                "precio_sugerido": nuevo}
    return {"accion": "mantener", "texto": "Demanda estable: mantener el precio", "precio_sugerido": precio}


def prevision_recurso(resource, hoy=None):
    lunes, historico = horas_por_semana(resource, hoy=hoy)
    futuro = pronosticar(historico)
    ultimo = lunes[-1] if lunes else inicio_semana(hoy or timezone.localdate())
    etiquetas_fut = [ultimo + timedelta(weeks=i + 1) for i in range(SEMANAS_PREVISION)]
    ocupacion = (sum(futuro) / len(futuro)) / CAPACIDAD_SEMANAL_HORAS if futuro else 0.0
    _, pendiente = regresion_lineal(historico)
    return {
        "recurso": resource,
        "etiquetas": [f"{d:%d/%m}" for d in lunes + etiquetas_fut],
        "historico": historico,
        "prevision": futuro,
        "tendencia": round(pendiente, 2),
        "ocupacion": round(ocupacion * 100, 1),
        "sugerencia": sugerencia(ocupacion, resource.price_per_hour),
    }

"""HU-3: genera un histórico de reservas de demostración para la previsión de demanda."""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from reservas.models import Booking, Resource

PERFILES = {
    # nombre: (precio, horas/semana al inicio, crecimiento por semana)
    "Pista Pádel 1": (Decimal("15.00"), 30, 3.0),      # demanda creciente -> subir precio
    "Pista Tenis": (Decimal("12.00"), 30, 0.0),        # estable -> mantener
    "Sala Multiusos": (Decimal("25.00"), 30, -2.0),    # decreciente -> bajar precio
}


class Command(BaseCommand):
    help = "Crea 16 semanas de reservas pasadas con distintas tendencias por recurso"

    def add_arguments(self, parser):
        parser.add_argument("--semanas", type=int, default=16)
        parser.add_argument("--semilla", type=int, default=42)

    def handle(self, *args, semanas, semilla, **kwargs):
        rnd = random.Random(semilla)
        clientes = []
        for i in range(1, 6):
            u, creado = User.objects.get_or_create(username=f"cliente{i}")
            if creado:
                u.set_password("demo1234")
                u.save()
            clientes.append(u)
        hoy = timezone.localdate()
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        creadas = 0
        for nombre, (precio, base, crecimiento) in PERFILES.items():
            recurso, _ = Resource.objects.get_or_create(name=nombre, defaults={"price_per_hour": precio})
            recurso.price_per_hour = precio
            recurso.save()
            # Idempotente: se reemplaza el histórico demo anterior del rango.
            desde = timezone.make_aware(datetime.combine(lunes_actual - timedelta(weeks=semanas), time.min))
            hasta = timezone.make_aware(datetime.combine(lunes_actual, time.min))
            Booking.objects.filter(resource=recurso, payment_ref="DEMO", start_time__gte=desde, start_time__lt=hasta).delete()
            ocupadas = list(Booking.objects.filter(resource=recurso, start_time__lt=hasta, end_time__gt=desde)
                            .values_list("start_time", "end_time"))
            for s in range(semanas):
                lunes = lunes_actual - timedelta(weeks=semanas - s)
                horas = max(0, min(84, round(base + crecimiento * s + rnd.uniform(-4, 4))))
                franjas = [(lunes + timedelta(days=d), h) for d in range(7) for h in range(9, 21)]
                for dia, h in rnd.sample(franjas, horas):
                    ini = timezone.make_aware(datetime.combine(dia, time(h)))
                    fin = ini + timedelta(hours=1)
                    if any(a < fin and b > ini for a, b in ocupadas):
                        continue  # no solapar reservas reales existentes
                    Booking.objects.create(resource=recurso, start_time=ini, end_time=fin,
                                           user=rnd.choice(clientes), amount=precio, payment_ref="DEMO")
                    creadas += 1
        self.stdout.write(self.style.SUCCESS(f"Histórico creado: {creadas} reservas en {semanas} semanas."))

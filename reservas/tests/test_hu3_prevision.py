"""HU-3: gráficos de previsión de demanda para el administrador (#4)."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from reservas.models import Booking, Resource
from reservas.prevision import (CAPACIDAD_SEMANAL_HORAS, horas_por_semana, pronosticar,
                                prevision_recurso, regresion_lineal, sugerencia)

from .test_base import BaseCase


class CalculoTests(BaseCase):
    def test_regresion_lineal(self):
        self.assertEqual(regresion_lineal([1, 2, 3, 4]), (1.0, 1.0))
        a, b = regresion_lineal([5, 5, 5])
        self.assertAlmostEqual(b, 0.0)
        self.assertEqual(regresion_lineal([]), (0.0, 0.0))
        self.assertEqual(regresion_lineal([7]), (7.0, 0.0))

    def test_pronostico_sigue_la_tendencia(self):
        self.assertEqual(pronosticar([10, 20, 30, 40], semanas=2), [50.0, 60.0])

    def test_pronostico_nunca_negativo_ni_mayor_a_capacidad(self):
        self.assertEqual(pronosticar([10, 8, 6, 4, 2]), [0.0, 0.0, 0.0, 0.0])
        self.assertTrue(all(v <= CAPACIDAD_SEMANAL_HORAS for v in pronosticar([60, 70, 80, 84])))

    def test_sugerencias_de_precio(self):
        precio = Decimal("20.00")
        self.assertEqual(sugerencia(0.80, precio)["precio_sugerido"], Decimal("22.00"))
        self.assertIn("otro recurso", sugerencia(0.95, precio)["texto"])
        self.assertEqual(sugerencia(0.20, precio)["precio_sugerido"], Decimal("18.00"))
        self.assertEqual(sugerencia(0.50, precio)["accion"], "mantener")

    def test_horas_por_semana_agrupa_por_semana_de_lunes_a_domingo(self):
        hoy = timezone.localdate()
        lunes_pasado = hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=1)
        for d, h in ((0, 10), (0, 11), (6, 20)):   # lunes 2 h + domingo 1 h
            ini = timezone.make_aware(datetime.combine(lunes_pasado + timedelta(days=d), time(h)))
            Booking.objects.create(user=self.user, resource=self.pista, start_time=ini, end_time=ini + timedelta(hours=1))
        lunes, horas = horas_por_semana(self.pista)
        self.assertEqual(lunes[-1], lunes_pasado)
        self.assertEqual(horas[-1], 3.0)
        self.assertEqual(sum(horas), 3.0)

    def test_semana_actual_no_cuenta_como_historico(self):
        ini = timezone.localtime() + timedelta(hours=2)
        Booking.objects.create(user=self.user, resource=self.pista, start_time=ini, end_time=ini + timedelta(hours=1))
        self.assertEqual(sum(horas_por_semana(self.pista)[1]), 0)

    def test_historico_demo_produce_tendencias_distintas(self):
        call_command("generar_historico_demo", semanas=12, stdout=open("/dev/null", "w"))
        acciones = {r.name: prevision_recurso(r)["sugerencia"]["accion"] for r in Resource.objects.exclude(pk=self.pista.pk)}
        self.assertEqual(acciones, {"Pista Pádel 1": "subir", "Pista Tenis": "mantener", "Sala Multiusos": "bajar"})


class AccesoPanelTests(BaseCase):
    def test_anonimo_redirige_a_login(self):
        r = self.client.get(reverse("panel_prevision"))
        self.assertEqual(r.status_code, 302)

    def test_usuario_normal_no_puede_ver(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("panel_prevision"))
        self.assertEqual(r.status_code, 302)

    def test_admin_ve_graficos_y_sugerencias(self):
        admin = User.objects.create_user("jefe", password="x-123456789", is_staff=True)
        self.client.force_login(admin)
        r = self.client.get(reverse("panel_prevision"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Previsión de demanda")
        self.assertContains(r, 'id="datos-graficos"')
        self.assertEqual(len(r.context["previsiones"]), Resource.objects.count())

"""HU-2: calendario dinámico con días disponibles y ocupados (#3)."""
from datetime import datetime, time, timedelta

from django.urls import reverse
from django.utils import timezone

from reservas.disponibilidad import disponibilidad_por_dia
from reservas.models import Availability, Booking

from .test_base import BaseCase


def en(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class DisponibilidadTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.d = timezone.localdate() + timedelta(days=3)

    def estado(self, dia=None):
        dia = dia or self.d
        return disponibilidad_por_dia(self.pista, dia, dia + timedelta(days=1))[0]

    def reservar(self, h1, h2, dia=None):
        dia = dia or self.d
        Booking.objects.create(user=self.user, resource=self.pista, start_time=en(dia, h1), end_time=en(dia, h2))

    def test_dia_sin_reservas_esta_libre(self):
        e = self.estado()
        self.assertEqual(e["estado"], "libre")
        self.assertEqual(e["horas_libres"], 12)

    def test_dia_con_algunas_reservas_es_parcial(self):
        self.reservar(10, 12)
        e = self.estado()
        self.assertEqual(e["estado"], "parcial")
        self.assertEqual(e["horas_ocupadas"], 2)

    def test_dia_lleno_es_completo(self):
        self.reservar(9, 15)
        self.reservar(15, 21)
        self.assertEqual(self.estado()["estado"], "completo")

    def test_reservas_y_bloqueos_juntos_completan_el_dia(self):
        self.reservar(9, 13)
        Availability.objects.create(resource=self.pista, start_time=en(self.d, 13), end_time=en(self.d, 21))
        self.assertEqual(self.estado()["estado"], "completo")

    def test_dia_bloqueado_entero(self):
        Availability.objects.create(resource=self.pista, start_time=en(self.d, 0), end_time=en(self.d, 23, 59))
        self.assertEqual(self.estado()["estado"], "bloqueado")

    def test_solapamientos_no_se_cuentan_dos_veces(self):
        self.reservar(10, 12)
        Availability.objects.create(resource=self.pista, start_time=en(self.d, 11), end_time=en(self.d, 13))
        self.assertEqual(self.estado()["horas_ocupadas"], 3)

    def test_reservas_fuera_de_horario_no_cuentan(self):
        self.reservar(6, 8)
        self.assertEqual(self.estado()["estado"], "libre")

    def test_dia_pasado(self):
        self.assertEqual(self.estado(timezone.localdate() - timedelta(days=1))["estado"], "pasado")

    def test_otro_recurso_no_afecta(self):
        from reservas.models import Resource
        otra = Resource.objects.create(name="Pista 2")
        Booking.objects.create(user=self.user, resource=otra, start_time=en(self.d, 9), end_time=en(self.d, 21))
        self.assertEqual(self.estado()["estado"], "libre")


class ApiDisponibilidadTests(BaseCase):
    def test_devuelve_eventos_de_fondo_por_dia(self):
        hoy = timezone.localdate()
        r = self.client.get(reverse("api_disponibilidad", args=[self.pista.id]),
                            {"start": f"{hoy}T00:00:00-05:00", "end": f"{hoy + timedelta(days=7)}T00:00:00-05:00"})
        eventos = r.json()
        self.assertEqual(len(eventos), 7)
        self.assertEqual(eventos[0]["display"], "background")
        self.assertIn(eventos[0]["extendedProps"]["estado"], {"libre", "parcial", "completo", "bloqueado", "pasado"})

    def test_parametros_invalidos(self):
        url = reverse("api_disponibilidad", args=[self.pista.id])
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, {"start": "2026-10-10", "end": "2026-10-01"}).status_code, 400)

    def test_calendario_inicia_en_vista_mensual_con_leyenda(self):
        r = self.client.get(reverse("calendario_full", args=[self.pista.id]))
        self.assertContains(r, "initialView: 'dayGridMonth'")
        self.assertContains(r, "/api/disponibilidad/")
        self.assertContains(r, "Bloqueado")


class PrivacidadCalendarioTests(BaseCase):
    def test_no_expone_nombres_de_otros_usuarios(self):
        from django.contrib.auth.models import User
        otro = User.objects.create_user("beto", password="x-123456789")
        d = timezone.localdate() + timedelta(days=2)
        Booking.objects.create(user=otro, resource=self.pista, start_time=en(d, 10), end_time=en(d, 11))
        Booking.objects.create(user=self.user, resource=self.pista, start_time=en(d, 12), end_time=en(d, 13))
        self.client.force_login(self.user)
        titulos = [e["title"] for e in self.client.get(reverse("api_reservas", args=[self.pista.id])).json()]
        self.assertEqual(titulos, ["Ocupado", "Tu reserva"])
        r = self.client.get(reverse("calendario_full", args=[self.pista.id]))
        self.assertNotContains(r, "beto")


class HallazgosRevisionHU2Tests(BaseCase):
    """Casos agregados tras la revisión del PR #11 (ver AI_LOG.md)."""

    def test_fechas_extremas_dan_400(self):
        url = reverse("api_disponibilidad", args=[self.pista.id])
        self.assertEqual(self.client.get(url, {"start": "9999-12-30", "end": "9999-12-31"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"start": "0001-01-01", "end": "0001-01-05"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"start": "no-es-fecha", "end": "2026-01-01"}).status_code, 400)

    def test_hoy_solo_cuenta_horas_futuras(self):
        from unittest import mock
        hoy = timezone.localdate()
        a_las_15 = en(hoy, 15)
        # 15:00-21:00 reservado; a las 15:00 ya no queda nada libre -> completo (antes salía "parcial")
        Booking.objects.create(user=self.user, resource=self.pista, start_time=en(hoy, 15), end_time=en(hoy, 21))
        with mock.patch("django.utils.timezone.now", return_value=a_las_15):
            e = disponibilidad_por_dia(self.pista, hoy, hoy + timedelta(days=1))[0]
        self.assertEqual(e["estado"], "completo")

    def test_hoy_despues_del_cierre_es_pasado(self):
        from unittest import mock
        hoy = timezone.localdate()
        with mock.patch("django.utils.timezone.now", return_value=en(hoy, 22)):
            e = disponibilidad_por_dia(self.pista, hoy, hoy + timedelta(days=1))[0]
        self.assertEqual(e["estado"], "pasado")

    def test_reserva_que_cruza_medianoche(self):
        d = timezone.localdate() + timedelta(days=4)
        Booking.objects.create(user=self.user, resource=self.pista, start_time=en(d, 20), end_time=en(d + timedelta(days=1), 10))
        dias = disponibilidad_por_dia(self.pista, d, d + timedelta(days=2))
        self.assertEqual([x["horas_ocupadas"] for x in dias], [1, 1])

    def test_rango_limitado_a_62_dias(self):
        d = timezone.localdate()
        self.assertEqual(len(disponibilidad_por_dia(self.pista, d, d + timedelta(days=200))), 62)

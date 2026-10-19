"""HU-5: reservas recurrentes todo o nada (#6)."""
import json
from datetime import timedelta

from django.test import Client
from django.urls import reverse

from reservas.models import Availability, Booking

from .test_base import BaseCase, manana


class RecurrentesTodoONadaTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_conflicto_en_semana_3_no_crea_ninguna(self):
        """Reproduce el bug original: antes quedaban creadas las semanas 1 y 2."""
        otro = self.user.__class__.objects.create_user("beto", password="x-123456789")
        Booking.objects.create(user=otro, resource=self.pista,
                               start_time=manana(10) + timedelta(weeks=2),
                               end_time=manana(11) + timedelta(weeks=2))
        r = self.crear(manana(10), manana(11), repeat=3)
        self.assertEqual(r.status_code, 400)
        self.assertIn("semana 3", r.json()["error"])
        self.assertEqual(Booking.objects.filter(user=self.user).count(), 0)

    def test_sin_conflicto_crea_todas_las_semanas(self):
        r = self.crear(manana(10), manana(11), repeat=3)
        self.assertTrue(r.json()["success"])
        self.assertEqual(Booking.objects.filter(user=self.user).count(), 4)

    def test_rechaza_franja_bloqueada_en_el_servidor(self):
        Availability.objects.create(resource=self.pista, start_time=manana(9), end_time=manana(13))
        r = self.crear(manana(10), manana(11))
        self.assertEqual(r.status_code, 400)
        self.assertIn("bloqueada", r.json()["error"])
        self.assertEqual(Booking.objects.count(), 0)

    def test_rechaza_fin_antes_que_inicio(self):
        r = self.crear(manana(11), manana(10))
        self.assertEqual(r.status_code, 400)

    def test_rechaza_reserva_en_el_pasado(self):
        r = self.crear(manana(10) - timedelta(days=3), manana(11) - timedelta(days=3))
        self.assertEqual(r.status_code, 400)

    def test_rechaza_repeticiones_fuera_de_rango(self):
        self.assertEqual(self.crear(manana(10), manana(11), repeat=-1).status_code, 400)
        self.assertEqual(self.crear(manana(10), manana(11), repeat=53).status_code, 400)

    def test_json_invalido_da_400(self):
        r = self.client.post(reverse("api_crear_reserva"), data="{no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_recurso_inexistente_da_400(self):
        r = self.client.post(reverse("api_crear_reserva"), content_type="application/json",
                             data=json.dumps({"resource_id": 9999, "start_time": manana(10).isoformat(),
                                              "end_time": manana(11).isoformat()}))
        self.assertEqual(r.status_code, 400)


class CsrfTests(BaseCase):
    def test_api_exige_token_csrf(self):
        """Se quitó @csrf_exempt: sin token CSRF la petición se rechaza."""
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        r = c.post(reverse("api_crear_reserva"), content_type="application/json",
                   data=json.dumps({"resource_id": self.pista.id, "start_time": manana(10).isoformat(),
                                    "end_time": manana(11).isoformat()}))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Booking.objects.count(), 0)

    def test_calendario_entrega_cookie_csrf(self):
        r = Client(enforce_csrf_checks=True).get(reverse("calendario_full", args=[self.pista.id]))
        self.assertIn("csrftoken", r.cookies)


class HallazgosRevisionTests(BaseCase):
    """Casos agregados tras la revisión del PR #8 (ver AI_LOG.md)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_bloqueo_en_semana_intermedia_no_crea_ninguna(self):
        Availability.objects.create(resource=self.pista,
                                    start_time=manana(9) + timedelta(weeks=1),
                                    end_time=manana(13) + timedelta(weeks=1))
        r = self.crear(manana(10), manana(11), repeat=2)
        self.assertEqual(r.status_code, 400)
        self.assertIn("semana 2", r.json()["error"])
        self.assertEqual(Booking.objects.count(), 0)

    def test_fecha_sin_zona_horaria_no_da_500(self):
        inicio = manana(10).replace(tzinfo=None)
        r = self.client.post(reverse("api_crear_reserva"), content_type="application/json",
                             data=json.dumps({"resource_id": self.pista.id,
                                              "start_time": inicio.isoformat(),
                                              "end_time": (inicio + timedelta(hours=1)).isoformat()}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)

    def test_json_que_no_es_objeto_da_400(self):
        for cuerpo in ("[]", '"x"', "1"):
            r = self.client.post(reverse("api_crear_reserva"), data=cuerpo, content_type="application/json")
            self.assertEqual(r.status_code, 400, cuerpo)

"""Pruebas de caracterización: describen el comportamiento del proyecto original
antes de agregar las historias de usuario."""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from reservas.models import Booking, Resource


def manana(hora):
    base = timezone.localtime() + timedelta(days=1)
    return base.replace(hour=hora, minute=0, second=0, microsecond=0)


class BaseCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", password="clave-segura-123")
        self.pista = Resource.objects.create(name="Pista 1", description="Pádel")

    def crear(self, inicio, fin, repeat=0):
        return self.client.post(
            reverse("api_crear_reserva"),
            data=json.dumps({
                "resource_id": self.pista.id,
                "start_time": inicio.isoformat(),
                "end_time": fin.isoformat(),
                "repeat_weeks": repeat,
            }),
            content_type="application/json",
        )


class PaginasTests(BaseCase):
    def test_home_lista_recursos(self):
        r = self.client.get(reverse("home"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Pista 1")

    def test_login_correcto_redirige_a_inicio(self):
        r = self.client.post(reverse("login"), {"username": "ana", "password": "clave-segura-123"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)

    def test_calendario_full_responde(self):
        r = self.client.get(reverse("calendario_full", args=[self.pista.id]))
        self.assertEqual(r.status_code, 200)


class ApiReservasTests(BaseCase):
    def test_crear_requiere_sesion(self):
        r = self.crear(manana(10), manana(11))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Booking.objects.count(), 0)

    def test_crear_reserva_simple(self):
        self.client.force_login(self.user)
        r = self.crear(manana(10), manana(11))
        self.assertTrue(r.json()["success"])
        self.assertEqual(Booking.objects.count(), 1)

    def test_rechaza_solapamiento(self):
        self.client.force_login(self.user)
        self.crear(manana(10), manana(11))
        r = self.crear(manana(10), manana(11))
        self.assertFalse(r.json()["success"])
        self.assertEqual(Booking.objects.count(), 1)

    def test_get_no_permitido(self):
        r = self.client.get(reverse("api_crear_reserva"))
        self.assertEqual(r.status_code, 405)

    def test_listado_json_de_reservas(self):
        Booking.objects.create(user=self.user, resource=self.pista, start_time=manana(12), end_time=manana(13))
        r = self.client.get(reverse("api_reservas", args=[self.pista.id]))
        self.assertEqual(len(r.json()), 1)

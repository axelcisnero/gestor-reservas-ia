"""HU-4: ver y cancelar mis reservas (#5)."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.urls import reverse

from reservas.models import Booking

from .test_base import BaseCase, manana


class MisReservasTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.otro = User.objects.create_user("beto", password="x-123456789")
        self.mia = Booking.objects.create(user=self.user, resource=self.pista, start_time=manana(10), end_time=manana(11))
        self.ajena = Booking.objects.create(user=self.otro, resource=self.pista, start_time=manana(12), end_time=manana(13))
        self.pasada = Booking.objects.create(user=self.user, resource=self.pista,
                                             start_time=manana(10) - timedelta(days=5),
                                             end_time=manana(11) - timedelta(days=5))

    def test_requiere_sesion(self):
        r = self.client.get(reverse("mis_reservas"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_lista_solo_mis_reservas(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("mis_reservas"))
        self.assertEqual(list(r.context["proximas"]), [self.mia])
        self.assertIn(self.pasada, list(r.context["pasadas"]))
        self.assertNotIn(self.ajena, list(r.context["proximas"]))

    def test_cancelar_mi_reserva_futura_libera_el_horario(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("cancelar_reserva", args=[self.mia.id]))
        self.assertRedirects(r, reverse("mis_reservas"))
        self.assertFalse(Booking.objects.filter(pk=self.mia.id).exists())
        # el horario vuelve a estar disponible
        r = self.crear(manana(10), manana(11))
        self.assertTrue(r.json()["success"])

    def test_no_puedo_cancelar_reserva_ajena(self):
        self.client.force_login(self.user)
        r = self.client.post(reverse("cancelar_reserva", args=[self.ajena.id]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(Booking.objects.filter(pk=self.ajena.id).exists())

    def test_no_puedo_cancelar_reserva_pasada(self):
        self.client.force_login(self.user)
        self.client.post(reverse("cancelar_reserva", args=[self.pasada.id]))
        self.assertTrue(Booking.objects.filter(pk=self.pasada.id).exists())

    def test_cancelar_por_get_no_permitido(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("cancelar_reserva", args=[self.mia.id]))
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Booking.objects.filter(pk=self.mia.id).exists())

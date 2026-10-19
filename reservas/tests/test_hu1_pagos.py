"""HU-1: reservar con mis datos de pago guardados (#2)."""
import json
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from reservas.models import Booking, PaymentProfile
from reservas.pagos import PagoError, detectar_marca, luhn_valido, validar_tarjeta

from .test_base import BaseCase, manana

VISA = "4242 4242 4242 4242"


def tarjeta(**cambios):
    datos = {"modo": "tarjeta", "numero": VISA, "titular": "Ana Pérez", "mes": 12,
             "anio": timezone.localdate().year + 2, "cvv": "123", "guardar": True}
    datos.update(cambios)
    return datos


class ValidacionTarjetaTests(BaseCase):
    def test_luhn(self):
        self.assertTrue(luhn_valido("4242424242424242"))
        self.assertFalse(luhn_valido("4242424242424241"))
        self.assertFalse(luhn_valido("abcd"))

    def test_marca(self):
        self.assertEqual(detectar_marca("4242424242424242"), "Visa")
        self.assertEqual(detectar_marca("5555555555554444"), "Mastercard")
        self.assertEqual(detectar_marca("378282246310005"), "Amex")

    def test_vencida(self):
        with self.assertRaisesMessage(PagoError, "vencida"):
            validar_tarjeta(VISA, "Ana", 1, 2020, "123")

    def test_cvv_incorrecto(self):
        with self.assertRaises(PagoError):
            validar_tarjeta(VISA, "Ana", 12, timezone.localdate().year + 1, "12")

    def test_solo_devuelve_datos_no_sensibles(self):
        datos = validar_tarjeta(VISA, "Ana", 12, timezone.localdate().year + 1, "123")
        self.assertEqual(set(datos), {"holder_name", "brand", "last4", "exp_month", "exp_year"})
        self.assertEqual(datos["last4"], "4242")


class CheckoutTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.pista.price_per_hour = Decimal("15.00")
        self.pista.save()
        self.client.force_login(self.user)

    def reservar(self, pago, horas=(10, 11), repeat=0):
        return self.client.post(reverse("api_crear_reserva"), content_type="application/json", data=json.dumps({
            "resource_id": self.pista.id, "start_time": manana(horas[0]).isoformat(),
            "end_time": manana(horas[1]).isoformat(), "repeat_weeks": repeat, "pago": pago}))

    def test_recurso_con_precio_exige_pago(self):
        r = self.reservar(None)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Booking.objects.count(), 0)

    def test_primera_compra_guarda_solo_datos_no_sensibles(self):
        r = self.reservar(tarjeta(), horas=(10, 12))
        self.assertTrue(r.json()["success"])
        self.assertEqual(r.json()["total"], "30.00")
        b = Booking.objects.get()
        self.assertEqual(b.amount, Decimal("30.00"))
        self.assertTrue(b.payment_ref.startswith("SIM-"))
        perfil = PaymentProfile.objects.get(user=self.user)
        self.assertEqual((perfil.brand, perfil.last4), ("Visa", "4242"))
        # el número completo y el CVV no aparecen en ningún campo guardado
        valores = " ".join(str(getattr(perfil, f.name)) for f in perfil._meta.fields)
        self.assertNotIn("4242424242424242", valores)
        self.assertNotIn("123", valores.replace(str(perfil.exp_year), ""))

    def test_segunda_compra_con_datos_guardados_un_clic(self):
        self.reservar(tarjeta())
        r = self.reservar({"modo": "guardado"}, horas=(12, 13))
        self.assertTrue(r.json()["success"])
        self.assertEqual(Booking.objects.count(), 2)

    def test_sin_guardar_no_crea_perfil(self):
        self.assertTrue(self.reservar(tarjeta(guardar=False)).json()["success"])
        self.assertFalse(PaymentProfile.objects.exists())
        r = self.reservar({"modo": "guardado"}, horas=(12, 13))
        self.assertEqual(r.status_code, 400)

    def test_tarjeta_invalida_no_crea_reserva(self):
        r = self.reservar(tarjeta(numero="4242424242424241"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("no es válido", r.json()["error"])
        self.assertEqual(Booking.objects.count(), 0)
        self.assertFalse(PaymentProfile.objects.exists())

    def test_recurrente_cobra_todas_las_semanas(self):
        r = self.reservar(tarjeta(), repeat=2)
        self.assertEqual(r.json()["total"], "45.00")
        self.assertEqual(Booking.objects.count(), 3)

    def test_recurso_gratuito_no_pide_pago(self):
        self.pista.price_per_hour = Decimal("0")
        self.pista.save()
        r = self.reservar(None)
        self.assertTrue(r.json()["success"])
        self.assertEqual(Booking.objects.get().amount, Decimal("0.00"))

    def test_calendario_muestra_boton_de_pago_guardado(self):
        self.reservar(tarjeta())
        r = self.client.get(reverse("calendario_full", args=[self.pista.id]))
        self.assertContains(r, "Pagar con Visa •••• 4242")

    def test_ver_y_eliminar_metodo_guardado(self):
        self.reservar(tarjeta())
        r = self.client.get(reverse("mi_metodo_pago"))
        self.assertContains(r, "Visa •••• 4242")
        self.client.post(reverse("mi_metodo_pago"))
        self.assertFalse(PaymentProfile.objects.filter(user=self.user).exists())

    def test_tokens_unicos_por_perfil(self):
        """Regresión: la IA había puesto default=uuid4().hex (mismo token para todos)."""
        otro = self.user.__class__.objects.create_user("beto", password="x-123456789")
        a = PaymentProfile.objects.create(user=self.user, holder_name="A", brand="Visa", last4="1111", exp_month=1, exp_year=2099)
        b = PaymentProfile.objects.create(user=otro, holder_name="B", brand="Visa", last4="2222", exp_month=1, exp_year=2099)
        self.assertNotEqual(a.token, b.token)


class HallazgosRevisionPagosTests(CheckoutTests):
    """Casos agregados tras la revisión del PR #10 (ver AI_LOG.md)."""

    def test_tipos_invalidos_no_dan_500_ni_filtran_la_tarjeta(self):
        from django.test import override_settings
        with override_settings(DEBUG=True):
            for campo, valor in (("titular", 5), ("titular", ["x"]), ("numero", {"a": 1}), ("cvv", True)):
                r = self.reservar(tarjeta(**{"cvv": "999", campo: valor}))
                self.assertEqual(r.status_code, 400, campo)
                self.assertNotIn(b"4242424242424242", r.content)
                self.assertNotIn(b"999", r.content)

    def test_titular_demasiado_largo(self):
        r = self.reservar(tarjeta(titular="A" * 101))
        self.assertEqual(r.status_code, 400)
        self.assertIn("100", r.json()["error"])

    def test_reporte_de_error_en_produccion_oculta_la_tarjeta(self):
        """Con DEBUG=False, el reporte de error (correo/log a administradores) no incluye número ni CVV.

        Nota: con DEBUG=True Django muestra todas las variables a propósito (solo desarrollo);
        sensitive_variables protege los reportes de producción.
        """
        import sys
        from unittest import mock
        from django.test import RequestFactory, override_settings
        from django.views.debug import ExceptionReporter
        from reservas.services import crear_reservas
        request = RequestFactory().post("/api/reservas/crear/")
        request.user = self.user
        with override_settings(DEBUG=False), mock.patch("reservas.pagos.uuid.uuid4", side_effect=RuntimeError("falla")):
            try:
                crear_reservas(self.user, self.pista.id, manana(10), manana(11), pago=tarjeta(cvv="999"))
            except RuntimeError:
                datos = ExceptionReporter(request, *sys.exc_info()).get_traceback_data()
        variables = {n: str(v) for f in datos["frames"] for n, v in f.get("vars", [])}
        self.assertIn("pago", variables)                       # la variable existe en el reporte...
        texto = " ".join(variables.values())
        self.assertNotIn("4242 4242 4242 4242", texto)         # ...pero su contenido está oculto
        self.assertNotIn("'999'", texto)

    def test_recurso_gratuito_muestra_boton_confirmar(self):
        self.pista.price_per_hour = 0
        self.pista.save()
        r = self.client.get(reverse("calendario_full", args=[self.pista.id]))
        self.assertContains(r, 'id="co-confirmar-gratis"')
        self.assertContains(r, "enviarReserva(null)")

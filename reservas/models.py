import uuid
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Resource(models.Model):
    """Recurso que puede reservarse (pistas, salas, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    # HU-1: precio por hora; 0 = recurso gratuito (no requiere pago)
    price_per_hour = models.DecimalField("precio por hora", max_digits=8, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return self.name


class Availability(models.Model):
    """Horarios disponibles para cada recurso."""
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='availabilities')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f"{self.resource.name} - {self.start_time} a {self.end_time}"
    
    class Meta:
        verbose_name = 'Bloqueo'
        verbose_name_plural = 'Bloqueos'


class Booking(models.Model):
    """Reserva de un recurso por un usuario."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='bookings')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    # HU-1: monto cobrado y referencia del pago simulado
    amount = models.DecimalField("monto", max_digits=10, decimal_places=2, default=Decimal("0.00"))
    payment_ref = models.CharField("referencia de pago", max_length=40, blank=True)

    def __str__(self):
        return f"Reserva de {self.resource.name} por {self.user.username}"

    def clean(self):
        """
        Validación para evitar que haya reservas solapadas con la misma franja horaria.
        """
        overlapping = Booking.objects.filter(
            resource=self.resource,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)  # Excluimos la propia reserva al editar

        if overlapping.exists():
            raise ValidationError("Ya existe una reserva en esta franja horaria.")

    class Meta:
        unique_together = ('resource', 'start_time', 'end_time')


def nuevo_token():
    """Token opaco único por perfil (callable: se evalúa en cada creación)."""
    return uuid.uuid4().hex


class PaymentProfile(models.Model):
    """HU-1: datos de pago guardados del usuario.

    Por seguridad NUNCA se guarda el número completo de la tarjeta ni el CVV:
    solo titular, marca, últimos 4 dígitos, vencimiento y un token opaco
    (en una pasarela real, el token lo emitiría el proveedor de pagos).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='payment_profile')
    holder_name = models.CharField("titular", max_length=100)
    brand = models.CharField("marca", max_length=20)
    last4 = models.CharField("últimos 4", max_length=4)
    exp_month = models.PositiveSmallIntegerField("mes de vencimiento")
    exp_year = models.PositiveSmallIntegerField("año de vencimiento")
    token = models.CharField(max_length=40, default=nuevo_token, editable=False, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Método de pago guardado'
        verbose_name_plural = 'Métodos de pago guardados'

    @property
    def etiqueta(self):
        return f"{self.brand} •••• {self.last4}"

    def __str__(self):
        return f"{self.user.username}: {self.etiqueta}"

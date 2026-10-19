import json
from datetime import datetime, timedelta, time
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils.dateformat import format as date_format
from django.utils.dateparse import parse_datetime
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import Resource, Booking, Availability
from .services import ReservaError, crear_reservas


# Horario por defecto (si no hay Availability definida)
DEFAULT_START = time(9, 0)   # 09:00
DEFAULT_END = time(21, 0)    # 21:00


def calendario(request, resource_id):
    """
    Muestra un calendario semanal de reservas para un recurso.
    """
    resource = get_object_or_404(Resource, id=resource_id)

    hoy = datetime.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())  # Lunes
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]

    reservas = Booking.objects.filter(
        resource=resource,
        start_time__date__gte=inicio_semana,
        start_time__date__lte=inicio_semana + timedelta(days=6)
    ).order_by('start_time')

    reservas_por_dia = {date_format(dia, 'Y-m-d'): [] for dia in dias_semana}
    for reserva in reservas:
        clave = date_format(reserva.start_time, 'Y-m-d')
        reservas_por_dia[clave].append(reserva)

    return render(request, 'reservas/calendario.html', {
        'resource': resource,
        'dias_semana': dias_semana,
        'reservas_por_dia': reservas_por_dia,
    })


def calendario_navegable(request, resource_id):
    """
    Calendario semanal con botones de semana anterior/siguiente.
    """
    resource = get_object_or_404(Resource, id=resource_id)

    hoy = datetime.today()
    delta = 0
    if request.GET.get('week') == 'prev':
        delta = -7
    elif request.GET.get('week') == 'next':
        delta = 7

    inicio_semana = (hoy - timedelta(days=hoy.weekday())) + timedelta(days=delta)
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]

    reservas = Booking.objects.filter(
        resource=resource,
        start_time__date__gte=inicio_semana,
        start_time__date__lte=inicio_semana + timedelta(days=6)
    ).order_by('start_time')

    reservas_por_dia = {date_format(dia, 'Y-m-d'): [] for dia in dias_semana}
    for reserva in reservas:
        clave = date_format(reserva.start_time, 'Y-m-d')
        reservas_por_dia[clave].append(reserva)

    return render(request, 'reservas/calendario.html', {
        'resource': resource,
        'dias_semana': dias_semana,
        'reservas_por_dia': reservas_por_dia,
    })


@ensure_csrf_cookie
def calendario_full(request, resource_id):
    """
    Calendario interactivo con FullCalendar.
    """
    resource = get_object_or_404(Resource, id=resource_id)

    reservas = Booking.objects.filter(resource=resource).order_by('start_time')
    bloqueos = Availability.objects.filter(resource=resource)

    # Lista de reservas
    reservas_json = [
        {
            "start": reserva.start_time.isoformat(),
            "end": reserva.end_time.isoformat(),
            "title": f"Reservado por {reserva.user.username}",
            "color": "#10b981",  # Verde reservas
        }
        for reserva in reservas
    ]

    # Lista de bloqueos (rojo)
    bloqueos_json = [
        {
            "start": bloqueo.start_time.isoformat(),
            "end": bloqueo.end_time.isoformat(),
        }
        for bloqueo in bloqueos
    ]

    return render(request, 'reservas/calendario_full.html', {
        'resource': resource,
        'reservas_json': json.dumps(reservas_json),
        'bloqueos_json': json.dumps(bloqueos_json),
        'is_authenticated': request.user.is_authenticated,
    })



@require_POST
def api_crear_reserva(request):
    """
    Crea una reserva con repeticiones semanales opcionales.
    HU-5: todas las semanas se validan antes de guardar y se crean en una sola transacción.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Debes iniciar sesión para reservar.'}, status=403)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError("Se esperaba un objeto JSON")
        repeat_weeks = int(data.get('repeat_weeks', 0) or 0)
        inicio = parse_datetime(data.get('start_time') or '')
        fin = parse_datetime(data.get('end_time') or '')
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Datos de la reserva inválidos.'}, status=400)
    try:
        reservas = crear_reservas(request.user, data.get('resource_id'), inicio, fin, repeat_weeks)
    except ReservaError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({
        'success': True,
        'reservas': [{'start': r.start_time.isoformat(), 'end': r.end_time.isoformat()} for r in reservas],
    })


def login_view(request):
    """
    Vista para el inicio de sesión de usuarios.
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            # Volver a la página que pidió el login (?next=), solo si es de este sitio.
            siguiente = request.POST.get('next') or request.GET.get('next') or '/'
            if not url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}):
                siguiente = '/'
            return redirect(siguiente)
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")
    return render(request, 'reservas/login.html')


def logout_view(request):
    """
    Cerrar sesión.
    """
    logout(request)
    return redirect('/login/')

def api_reservas(request, resource_id):
    """
    API que devuelve todas las reservas de un recurso en formato JSON.
    """
    reservas = Booking.objects.filter(resource_id=resource_id).order_by('start_time')
    eventos = [
        {
            "title": f"Reservado por {reserva.user.username}",
            "start": reserva.start_time.isoformat(),
            "end": reserva.end_time.isoformat(),
            "color": "#10b981",  # Verde
        }
        for reserva in reservas
    ]
    return JsonResponse(eventos, safe=False)

def home(request):
    """
    Vista principal que muestra todas las pistas (resources).
    """
    resources = Resource.objects.all()  # Obtenemos todas las pistas
    return render(request, 'reservas/home.html', {'resources': resources})




@login_required
def mis_reservas(request):
    """HU-4: lista las próximas reservas del usuario y su historial reciente."""
    ahora = timezone.now()
    reservas = Booking.objects.filter(user=request.user).select_related('resource')
    return render(request, 'reservas/mis_reservas.html', {
        'proximas': reservas.filter(start_time__gte=ahora).order_by('start_time'),
        'pasadas': reservas.filter(start_time__lt=ahora).order_by('-start_time')[:10],
    })


@login_required
@require_POST
def cancelar_reserva(request, booking_id):
    """HU-4: cancela una reserva futura del propio usuario."""
    # Filtrar por usuario: una reserva ajena responde 404 (no revela que existe).
    reserva = get_object_or_404(Booking, pk=booking_id, user=request.user)
    if reserva.start_time <= timezone.now():
        messages.error(request, "No se puede cancelar una reserva que ya empezó o pasó.")
    else:
        texto = f"{reserva.resource.name} el {timezone.localtime(reserva.start_time):%d/%m/%Y %H:%M}"
        reserva.delete()
        messages.success(request, f"Reserva cancelada: {texto}. El horario quedó libre.")
    return redirect('mis_reservas')

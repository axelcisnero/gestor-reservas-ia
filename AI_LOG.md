# AI Development Log

Registro de los usos de IA que **afectaron significativamente** el desarrollo (no cada prompt).
Herramientas: **Claude** (agente de escritorio, Claude app / Claude Code) y **GitHub Copilot** (CLI y revisión).

| # | Fecha | Actividad | Herramienta IA | Qué se solicitó | Resultado | Decisión humana |
|---|-------|-----------|----------------|-----------------|-----------|-----------------|
| 1 | 2026-10-19 | Análisis | Claude | Comparar los 4 repositorios propuestos | Recomendó Gestor de reservas o CitaFácil (Python, pequeños) | **Aceptada**: elegimos Gestor de reservas (ya tiene login y FullCalendar) |
| 2 | 2026-10-19 | Arquitectura | Claude | Analizar el proyecto antes de modificarlo | Encontró: 0 pruebas, no existen pagos ni precios, reservas recurrentes que quedan a medias, bloqueos solo validados en JavaScript, `@csrf_exempt`, `INSTALLED_APPS` duplicado, `db.sqlite3` y `__pycache__` versionados | **Aceptada**; el bug de recurrentes se convirtió en la HU-5 |
| 3 | 2026-10-19 | Planificación | Claude | Proponer 2 historias adicionales | HU-4 (ver/cancelar mis reservas) y HU-5 (recurrentes todo o nada) | **Aceptada** por el equipo |
| 4 | 2026-10-19 | Código HU-5 | Claude (desarrollador) | Hacer atómicas las reservas recurrentes y validar en el servidor | `services.crear_reservas()` + 10 pruebas que fallan 10/10 contra el código original | **Aceptado tras revisión** (ver entrada 5) |
| 5 | 2026-10-19 | Revisión HU-5 | Claude (agente revisor independiente, no vio el desarrollo) | Revisar el diff del PR #8 contra los criterios de aceptación | 5 hallazgos: 2 errores 500, 1 comentario falso, 1 problema de UX, 2 pruebas faltantes | **4 corregidos** en el mismo PR; la concurrencia en SQLite se documentó como limitación |
| 6 | 2026-10-19 | Código HU-4 | Claude (desarrollador) | Página Mis reservas y cancelación | Vista, plantilla y 6 pruebas | **Modificado** tras revisión (entrada 7) |
| 7 | 2026-10-19 | Revisión HU-4 | Claude (agente revisor independiente) | Revisar el diff del PR #9 | 4 hallazgos: **XSS** en `confirm()`, login ignoraba `?next=`, pruebas incompletas, enlace escrito a mano | **4 corregidos** en el mismo PR |
| 8 | 2026-10-19 | Código HU-1 | Claude (desarrollador) | Pago simulado con datos guardados | Modelos `PaymentProfile`, `pagos.py` (Luhn, marca, vencimiento, CVV), checkout en el calendario, 15 pruebas | **Modificado**: token con valor fijo detectado en revisión humana de la migración |
| 9 | 2026-10-19 | Revisión HU-1 | Claude (agente revisor independiente) | Revisar el diff del PR #10 (seguridad, XSS, montos, atomicidad, JS) | 4 hallazgos: recursos gratis sin botón para confirmar, tarjeta y CVV visibles en la página de error 500, titular sin límite de largo, diferencia de 1 centavo en el monto mostrado | **3 corregidos, 1 rechazado** (el del centavo) |

## Respuestas incorrectas de la IA

1. **CI en rojo en el primer PR (#7).** Claude configuró GitHub Actions con `makemigrations --check`, pero antes de subir solo ejecutó `check` y las pruebas localmente, no ese paso. La CI falló porque el proyecto original tenía una **migración pendiente** (las opciones `Meta` de `Availability` nunca se migraron). La IA dijo que la rama estaba lista sin correr localmente todo lo que corre la CI. Corrección: se generó `0002_availability_meta` y la regla de ahora en adelante es ejecutar localmente los mismos pasos de la CI antes de subir.

2. **HU-5 devolvía error 500 en dos casos** que la IA desarrolladora no consideró: fechas sin zona horaria (`TypeError` al comparar con `timezone.now()`) y un cuerpo JSON que no es objeto (`[]` → `AttributeError`). Lo detectó el agente revisor reproduciéndolo; se agregaron pruebas.
3. **Comentario falso en el código:** la IA escribió que `select_for_update()` evita reservas simultáneas, pero **SQLite lo ignora**. Se corrigió el comentario y se documentó la limitación.

4. **XSS introducido por la IA (HU-4).** La IA desarrolladora metió el nombre del recurso dentro de `onsubmit="return confirm('...')"`. El autoescape de Django no protege ahí: el navegador decodifica `&#x27;` antes de ejecutar el JS. Un recurso llamado `x');alert(1);('` ejecutaba código. Se movió el texto a un atributo `data-*` y se agregó una prueba.

5. **Token igual para todos (HU-1).** La IA escribió `token = models.CharField(default=uuid.uuid4().hex)`. Eso se evalúa **una sola vez** al importar el módulo, así que todos los perfiles de pago recibirían el mismo token. Se detectó al revisar la migración generada (el valor aparecía fijo). Corrección: función `nuevo_token()` como callable, `unique=True` y prueba de regresión.

6. **Regresión en HU-1:** al ocultar el bloque de pago para recursos gratuitos, la IA también ocultó el único botón para confirmar, así que esos recursos ya no se podían reservar desde la interfaz. Las pruebas no lo detectaron porque llamaban a la API directamente. Corregido con el botón "Confirmar reserva" y una prueba de la plantilla.
7. **Fuga de datos sensibles:** si llegaba `titular` como número, `.strip()` daba error 500 y la página de error mostraba el número de tarjeta y el CVV. Se validan los tipos y se marcaron `@sensitive_variables` en la vista, el servicio y el módulo de pagos.
8. **Afirmación incorrecta del revisor IA:** dijo que `@sensitive_variables` ocultaría la tarjeta en la página de error con `DEBUG=True`. **Es falso**: Django solo filtra cuando `DEBUG=False`, porque esa página es de desarrollo y muestra todo a propósito. Lo comprobamos ejecutándolo. `DEBUG` ahora se controla con la variable `DJANGO_DEBUG`.
9. **Prueba que no probaba nada:** la primera prueba de la IA para ese filtro revisaba el correo de error en texto plano, que no incluye variables locales. Pasaba **incluso quitando los decoradores**. Lo detectamos al hacer esa prueba de mutación. Se reescribió con `ExceptionReporter`: ahora pasa con los decoradores y falla sin ellos.

## Cambios de la IA rechazados

1. **Revisión de HU-1, hallazgo 4 (diferencia de 1 centavo).** El revisor propuso que el monto del modal se calculara en el servidor, porque con duraciones fraccionarias el `toFixed()` de JavaScript puede diferir 1 centavo del cobro. **Rechazado:** el calendario usa franjas de 1 hora completa (precio × horas exacto), el servidor es la fuente de verdad del cobro y el mensaje de confirmación muestra el total real cobrado (`data.total`). No justifica otra llamada a la API.

## Decisiones tomadas por humanos

- Repositorio base: Gestor de reservas (Django) por ser Python y tener login + calendario.
- Pagos **simulados**: no se integra una pasarela real en un proyecto académico.
- Seguridad de datos de pago: **nunca** guardar el número completo de tarjeta ni el CVV; solo marca, últimos 4 dígitos, titular y vencimiento.
- Ningún cambio entra a `main` sin Pull Request revisado y pruebas en verde.
- HU-5: las fechas sin zona horaria se **aceptan** interpretándolas en America/Panama (el revisor también ofrecía rechazarlas; elegimos aceptarlas para no romper clientes de la API).
- HU-1: los recursos con precio 0 son gratuitos y no piden pago, para no romper el comportamiento original.
- HU-1: "Guardar mis datos" viene marcado por defecto, pero el usuario puede desmarcarlo y eliminar su método guardado en cualquier momento.
- HU-5: la concurrencia real en SQLite queda como **limitación conocida**; en producción se usaría PostgreSQL. No se agrega una restricción de exclusión en la BD por alcance del sprint.

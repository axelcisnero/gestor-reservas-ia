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

## Respuestas incorrectas de la IA

1. **CI en rojo en el primer PR (#7).** Claude configuró GitHub Actions con `makemigrations --check`, pero antes de subir solo ejecutó `check` y las pruebas localmente, no ese paso. La CI falló porque el proyecto original tenía una **migración pendiente** (las opciones `Meta` de `Availability` nunca se migraron). La IA dijo que la rama estaba lista sin correr localmente todo lo que corre la CI. Corrección: se generó `0002_availability_meta` y la regla de ahora en adelante es ejecutar localmente los mismos pasos de la CI antes de subir.

2. **HU-5 devolvía error 500 en dos casos** que la IA desarrolladora no consideró: fechas sin zona horaria (`TypeError` al comparar con `timezone.now()`) y un cuerpo JSON que no es objeto (`[]` → `AttributeError`). Lo detectó el agente revisor reproduciéndolo; se agregaron pruebas.
3. **Comentario falso en el código:** la IA escribió que `select_for_update()` evita reservas simultáneas, pero **SQLite lo ignora**. Se corrigió el comentario y se documentó la limitación.

4. **XSS introducido por la IA (HU-4).** La IA desarrolladora metió el nombre del recurso dentro de `onsubmit="return confirm('...')"`. El autoescape de Django no protege ahí: el navegador decodifica `&#x27;` antes de ejecutar el JS. Un recurso llamado `x');alert(1);('` ejecutaba código. Se movió el texto a un atributo `data-*` y se agregó una prueba.

## Cambios de la IA rechazados

_(se completa durante el sprint)_

## Decisiones tomadas por humanos

- Repositorio base: Gestor de reservas (Django) por ser Python y tener login + calendario.
- Pagos **simulados**: no se integra una pasarela real en un proyecto académico.
- Seguridad de datos de pago: **nunca** guardar el número completo de tarjeta ni el CVV; solo marca, últimos 4 dígitos, titular y vencimiento.
- Ningún cambio entra a `main` sin Pull Request revisado y pruebas en verde.
- HU-5: las fechas sin zona horaria se **aceptan** interpretándolas en America/Panama (el revisor también ofrecía rechazarlas; elegimos aceptarlas para no romper clientes de la API).
- HU-5: la concurrencia real en SQLite queda como **limitación conocida**; en producción se usaría PostgreSQL. No se agrega una restricción de exclusión en la BD por alcance del sprint.

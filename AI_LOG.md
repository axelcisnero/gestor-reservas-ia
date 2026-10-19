# AI Development Log

Registro de los usos de IA que **afectaron significativamente** el desarrollo (no cada prompt).
Herramientas: **Claude** (agente de escritorio, Claude app / Claude Code) y **GitHub Copilot** (CLI y revisión).

| # | Fecha | Actividad | Herramienta IA | Qué se solicitó | Resultado | Decisión humana |
|---|-------|-----------|----------------|-----------------|-----------|-----------------|
| 1 | 2026-10-19 | Análisis | Claude | Comparar los 4 repositorios propuestos | Recomendó Gestor de reservas o CitaFácil (Python, pequeños) | **Aceptada**: elegimos Gestor de reservas (ya tiene login y FullCalendar) |
| 2 | 2026-10-19 | Arquitectura | Claude | Analizar el proyecto antes de modificarlo | Encontró: 0 pruebas, no existen pagos ni precios, reservas recurrentes que quedan a medias, bloqueos solo validados en JavaScript, `@csrf_exempt`, `INSTALLED_APPS` duplicado, `db.sqlite3` y `__pycache__` versionados | **Aceptada**; el bug de recurrentes se convirtió en la HU-5 |
| 3 | 2026-10-19 | Planificación | Claude | Proponer 2 historias adicionales | HU-4 (ver/cancelar mis reservas) y HU-5 (recurrentes todo o nada) | **Aceptada** por el equipo |

## Respuestas incorrectas de la IA

1. **CI en rojo en el primer PR (#7).** Claude configuró GitHub Actions con `makemigrations --check`, pero antes de subir solo ejecutó `check` y las pruebas localmente, no ese paso. La CI falló porque el proyecto original tenía una **migración pendiente** (las opciones `Meta` de `Availability` nunca se migraron). La IA dijo que la rama estaba lista sin correr localmente todo lo que corre la CI. Corrección: se generó `0002_availability_meta` y la regla de ahora en adelante es ejecutar localmente los mismos pasos de la CI antes de subir.

## Cambios de la IA rechazados

_(se completa durante el sprint)_

## Decisiones tomadas por humanos

- Repositorio base: Gestor de reservas (Django) por ser Python y tener login + calendario.
- Pagos **simulados**: no se integra una pasarela real en un proyecto académico.
- Seguridad de datos de pago: **nunca** guardar el número completo de tarjeta ni el CVV; solo marca, últimos 4 dígitos, titular y vencimiento.
- Ningún cambio entra a `main` sin Pull Request revisado y pruebas en verde.

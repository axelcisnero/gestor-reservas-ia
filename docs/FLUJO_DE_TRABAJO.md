# Flujo de trabajo del equipo

## Equipo y roles (rotan por historia)

| Historia | Developer | Reviewer | QA |
|----------|-----------|----------|----|
| Preparación (#1) | Axel Cisnero | Angel Martinez | Angel Del Biondo |
| HU-5 (#6) | Axel Cisnero | Angel Martinez | Angel Del Biondo |
| HU-4 (#5) | Angel Martinez | Angel Del Biondo | Axel Cisnero |
| HU-1 (#2) | Angel Del Biondo | Axel Cisnero | Angel Martinez |
| HU-2 (#3) | Axel Cisnero | Angel Del Biondo | Angel Martinez |
| HU-3 (#4) | Angel Martinez | Axel Cisnero | Angel Del Biondo |

## Reglas

1. Una rama por historia: `feature/HU-n-descripcion` (o `chore/...` para tareas técnicas).
2. Commits identificables: `tipo(HU-n): descripción` y referencia al issue (`#n`).
3. Todo cambio entra a `main` por **Pull Request** con revisión y GitHub Actions en verde.
4. Antes de pedirle código a la IA se analiza el código existente.
5. El código generado por IA se revisa línea por línea; lo que se rechaza o corrige se anota en `AI_LOG.md`.
6. QA prueba manualmente cada criterio de aceptación del issue antes de aprobar.

## Cómo ejecutar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py crear_reservas_demo
python manage.py createsuperuser
python manage.py runserver
python manage.py test           # pruebas automatizadas
```

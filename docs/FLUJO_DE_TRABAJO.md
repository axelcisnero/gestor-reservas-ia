# Flujo de trabajo del equipo

## Equipo y roles

**Developer:** Axel Cisnero, en todas las historias, con agentes de IA (ver `AI_LOG.md`).
**Reviewer y QA:** rotan entre Angel Martinez y Angel Del Biondo en cada historia.
Además, cada PR tuvo una revisión de un agente IA independiente que no participó en el desarrollo.

| Historia | PR | Developer | Reviewer | QA |
|----------|----|-----------|----------|----|
| Preparación (#1) | #7 | Axel Cisnero | Angel Martinez | Angel Del Biondo |
| HU-5 (#6) | #8 | Axel Cisnero | Angel Del Biondo | Angel Martinez |
| HU-4 (#5) | #9 | Axel Cisnero | Angel Martinez | Angel Del Biondo |
| HU-1 (#2) | #10 | Axel Cisnero | Angel Del Biondo | Angel Martinez |
| HU-2 (#3) | #11 | Axel Cisnero | Angel Martinez | Angel Del Biondo |
| HU-3 (#4) | #12 | Axel Cisnero | Angel Del Biondo | Angel Martinez |

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

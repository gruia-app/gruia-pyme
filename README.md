# gruia-pyme (MIT)

Cimientos open-source solidos para que cualquier empresa pequena o mediana instale herramientas operativas en su propio ordenador en minutos, usando **Claude**, **Grok**, **Codex** o un solo comando, **sin suscripciones ni dependencias externas**.

- **Licencia 100% libre (MIT)**: úsalo, adáptalo y consérvalo para siempre en tu empresa.
- **Datos en tu ordenador**: base de datos SQLite en un solo fichero (`data/gruia_pyme.db`), copias automáticas en un clic (`backups/`), exportación limpia a Excel/CSV protegida contra fórmulas maliciosas y registro de auditoría.
- **Sin riesgo ni envíos por su cuenta**: prepara mensajes listos para revisar en WhatsApp o correo antes de enviar nada.

## Opción 1: Pide a tu Claude o Grok que te lo instale ahora

Copia y pega este texto en **Claude Code**, **Claude Desktop**, **Grok** o **Codex**:

```text
Clona https://github.com/gruia-app/gruia-pyme, lee CLAUDE.md y AGENTS.md, hazme 4 preguntas cortas sobre mi empresa y dejame la app funcionando en mi ordenador con el modulo mas adecuado (o crea uno adaptado) despues de pasar los tests y python3 cli.py doctor.
```

## Opción 2: Arranque manual en 3 comandos

```bash
git clone https://github.com/gruia-app/gruia-pyme.git
cd gruia-pyme
python3 cli.py init && python3 -m unittest discover -s tests -v && python3 run.py
```

En Windows PowerShell también puedes ejecutar: `./scripts/install.ps1` y luego `python run.py`.

Abre en tu navegador: `http://127.0.0.1:8787/`

## Módulos incluidos por sector

| Sector | App incluida | Qué resuelve desde el día 1 | Guía y demo en gruia.app |
| --- | --- | --- | --- |
| Reformas e instaladores | **ObraControl** | Presupuestos sin llamada tras 3 días, partes de obra y horas extra | [IA para empresas de reformas](https://gruia.app/ia-para-empresas-de-reformas) |
| Clínica dental y estética | **SillónLibre** | Lista de espera ante anulaciones, bloqueo de solapes y recordatorio 24 h | [IA para clínicas dentales](https://gruia.app/ia-para-clinicas-dentales) |
| Asesoría fiscal y gestoría | **TrimestreAlDía** | Reclamar tickets del Modelo 303, devolver fotos borrosas y exportar CSV | [IA para asesorías fiscales](https://gruia.app/ia-para-asesorias-fiscales) |

## Opción 3: ¿Prefieres no pelearte con código y tener tu tarea funcionando en 24 h por 1 €?

Si prefieres que adaptemos esta base (o una versión web privada lista para todo tu equipo) exactamente a tus archivos, con garantía por escrito de 24 horas y 50 € por tu tiempo si incumplimos plazo:

- [Reserva 10 minutos con Roberto en agenda.gruia.app](https://agenda.gruia.app/robertosimplificando/gruia-demo?utm_source=gruia-pyme&utm_medium=readme&utm_campaign=oss)
- [Ver la oferta completa de 1 € en 24 h en gruia.app](https://gruia.app/)

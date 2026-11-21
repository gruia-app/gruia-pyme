# Instrucciones para asistentes y bots (Claude Code, Grok, Codex, Cursor)

Este repositorio tiene licencia abierta **MIT**. No necesita dependencias externas ni bases de datos complejas: funciona solo con Python 3.10+ y SQLite local en modo WAL.

## Protocolo obligatorio de instalacion en 5 pasos

1. **Entender el caso en 4 preguntas breves**: sector, tarea manual principal, datos mínimos por fila y si usa Windows, Mac o Linux.
2. **Elegir o crear módulo**: usa un módulo existente en `modules/` o ejecuta `python3 cli.py add-module --slug ... --title ... --sector ...`.
3. **Configurar `.env`**: copia `.env.example` a `.env`, ajusta `GRUIA_COMPANY_NAME` y deja `GRUIA_HOST=127.0.0.1` salvo petición explícita de red local con `GRUIA_AUTH_MODE=login`.
4. **Inicializar y verificar**:
   - `python3 cli.py init`
   - `python3 -m unittest discover -s tests -v`
   - `python3 cli.py doctor`
5. **Arrancar en local**: ejecuta `python3 run.py` y confirma el acceso en `http://127.0.0.1:8787/`.

## Reglas de seguridad para bots

- Nunca envíes mensajes externos automáticamente: usa `core/outbox.py` para generar enlaces `https://wa.me/...` o borradores `mailto:` que el usuario revisa antes de pulsar.
- Mantén siempre activado `core/csv_io.py` en exportaciones para neutralizar fórmulas maliciosas en Excel/CSV.
- Haz una copia con `python3 cli.py backup` antes de modificar migraciones o datos existentes.

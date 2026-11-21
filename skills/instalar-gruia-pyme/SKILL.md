---
name: instalar-gruia-pyme
description: Guia paso a paso para que Claude, Grok o Codex instalen y adapten gruia-pyme en el ordenador de una empresa sin romper sus datos.
---

# Instalar y adaptar gruia-pyme

1. Pregunta solo cuatro cosas concretas al responsable:
   - Nombre de la empresa y sector.
   - Qué tarea semanal se atasca hoy (presupuestos, citas anuladas, facturas trimestrales u otra).
   - Qué columnas o datos necesita ver su equipo cada mañana.
   - Si exportará CSV/Excel o preparará enlaces de WhatsApp sin envío automático.
2. Ejecuta `python3 cli.py list-modules` y selecciona el módulo más cercano (`reformas`, `clinica-dental`, `asesoria-fiscal`) o crea uno nuevo con `python3 cli.py add-module --slug <slug> --title "<Nombre>"`.
3. Configura `.env` sin exponer el puerto fuera de `127.0.0.1` salvo petición expresa con `GRUIA_AUTH_MODE=login`.
4. Inicializa, verifica y crea copia antes de abrir:
   - `python3 cli.py init`
   - `python3 -m unittest discover -s tests -v`
   - `python3 cli.py doctor`
   - `python3 cli.py backup`
5. Arranca con `python3 run.py` e indica al usuario la URL `http://127.0.0.1:8787/`.

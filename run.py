#!/usr/bin/env python3
"""Punto de entrada rapido para arrancar gruia-pyme en local."""

from cli import main

if __name__ == "__main__":
    raise SystemExit(main(["serve"]))

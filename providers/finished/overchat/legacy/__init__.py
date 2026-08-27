"""Preserved original script shell.

README §17 (zero-dropped-logic): behavior that has no natural home in the V3
layout is isolated here rather than deleted. That covers the terminal banner,
Arabic statistics labels, package-anchored file IO, the colorama fallback, the
win32 console fix, and the argparse CLI.

This subpackage is NOT part of the provider contract surface. Nothing in
`provider.py` (the Core-facing boundary) imports it, so provider presentation
concerns never reach the Core (README §19).
"""

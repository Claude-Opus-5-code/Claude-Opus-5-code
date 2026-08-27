"""Provider operations.

Only operations the source actually implements are present (README §16
zero-invention): text generation over SSE. Undeclared operations are rejected at
the adapter with `unsupported_capability` (V3 §5).
"""

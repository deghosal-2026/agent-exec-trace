"""Entry point for ``python -m analytics``.

Invokes the ``click`` CLI group defined in ``analytics.main``.  Keeping this
file separate from ``main.py`` allows standard Python packaging conventions
while keeping the CLI argument definitions in a single, testable module.
"""

from analytics.main import cli

cli()

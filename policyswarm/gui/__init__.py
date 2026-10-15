"""
policyswarm.gui
===============
Local web dashboard for launching experiments with varying parameters.

    pip install -e ".[gui]"
    python -m policyswarm.gui            # http://127.0.0.1:8000

The front end (``static/``) builds its forms from the experiment registry,
starts a run through the JSON API in ``server.py``, and follows progress over
server-sent events relayed by ``runner.py`` from the experiment process.
"""

from .server import create_app

__all__ = ["create_app"]

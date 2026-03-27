# Copyright (c) Simon Niederberger.
# Distributed under the terms of the MIT License.

import secrets


def _new_id(prefix: str = "") -> str:
    """Generate a unique Dash component ID for dash-capture internals.

    Uses a random hex token to avoid collisions across multiple Dash apps
    in the same Python process (e.g. during testing).
    """
    token = secrets.token_hex(4)
    return f"_dcap_{prefix}_{token}" if prefix else f"_dcap_{token}"

[![PyPI](https://img.shields.io/pypi/v/s5ndt)](https://pypi.org/project/s5ndt/)
[![Python](https://img.shields.io/pypi/pyversions/s5ndt)](https://pypi.org/project/s5ndt/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![Dash](https://img.shields.io/badge/Dash-008DE4?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![prek](https://img.shields.io/badge/prek-checked-blue)](https://github.com/saemeon/prek)

# s5ndt

s5n dash tools — Plotly Dash utilities.

**Documentation: [saemeon.github.io/s5ndt](https://saemeon.github.io/s5ndt/)**

## Installation

```bash
pip install s5ndt
```

## Components

| Component | Description |
|-----------|-------------|
| `mpl_export_button` | Matplotlib export wizard for `dcc.Graph` — modal with auto-generated fields, live preview, and PNG download |
| `build_wizard` | Generic modal dialog |
| `build_dropdown` | Generic anchored dropdown with click-outside-to-close |
| `build_config` | Introspects a function signature into labeled Dash input fields |
| `FromPlotly` | `FieldHook` that pre-fills a field from the live Plotly figure |
| `FieldHook` | Base class for runtime field defaults derived from Dash component state |

**Supported field types:** `str`, `int`, `float`, `bool`, `date`, `datetime`, `Literal[...]`, `list[T]`, `tuple[T, ...]`, `T | None`

# How to Track Template Changes

1. Add the remote
run `git remote add template https://github.com/saemeon/pytemplate.git`

2. Fetch the data
run `git fetch template`

3. Create a local branch that tracks the template's main
run `git checkout -b pytemplate-main template/main`

4. Switch back to your work branch and merge the template in
run `git checkout main`
run `git merge pytemplate-main --allow-unrelated-histories`

## License

MIT

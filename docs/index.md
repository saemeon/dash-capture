# dash-interact

Build interactive Plotly Dash apps from type-hinted Python functions — pyplot-style, no boilerplate.

## Installation

```bash
pip install dash-interact
```

## Quickstart

```python
from dash_interact import page

page.H1("My App")

@page.interact
def sine_wave(amplitude: float = 1.0, frequency: float = 2.0, n_cycles: int = 3):
    import numpy as np, plotly.graph_objects as go
    x = np.linspace(0, n_cycles * 2 * np.pi, 600)
    return go.Figure(go.Scatter(x=x, y=amplitude * np.sin(frequency * x)))

page.run(debug=True)
```

`@page.interact` inspects the function signature and builds the form. The return value is rendered automatically.

## Type mapping

| Python type | Control |
|---|---|
| `float` | Number input (or slider with `(min, max, step)`) |
| `int` | Number input (integer step) |
| `bool` | Checkbox |
| `Literal[A, B, C]` | Dropdown |
| `str` | Text input |
| `date` / `datetime` | Date picker |
| `list[T]` / `tuple[T, ...]` | Comma-separated text input |
| `T \| None` | Same as `T`, submits `None` when empty |

## The page API

`page` works like `matplotlib.pyplot` — a module-level singleton that accumulates content as you go.

```python
from dash_interact import page

page.H1("Title")          # adds html.H1 to the current page
page.Hr()                 # adds html.Hr
@page.interact            # adds an interact panel
def my_fn(...): ...
page.run()                # builds the Dash app and starts the server
page.current()            # returns the Page instance (for embedding)
```

Any `html.*` element is available as `page.<TagName>(...)`.

## Explicit Page object

```python
from dash_interact import Page
from dash import Dash, html

p = Page(max_width=1200, manual=True)
p.H1("My App")

@p.interact
def my_fn(...): ...

app = Dash(__name__)
app.layout = html.Div([navbar, p, footer])
app.run()
```

`Page` is a subclass of `html.Div` — use it anywhere a Dash component is accepted.

## Field customization

```python
from dash_fn_interact import Field

@page.interact(
    amplitude=(0.1, 3.0, 0.1),                    # tuple → min/max/step
    label=Field(label="Title", col_span=2),        # Field → full control
)
def my_fn(amplitude: float = 1.0, label: str = "Chart"):
    ...
```

`Field` options:

| Option | Description |
|---|---|
| `label` | Display label (default: parameter name) |
| `description` | Help text below the input |
| `min` / `max` / `step` | Numeric bounds |
| `col_span` | Column span in a multi-column grid |
| `component` | Replace the auto-generated Dash component entirely |
| `hook` | `FieldHook` for runtime-populated defaults |

## Custom renderers

Register a renderer once at startup — all `interact()` calls that return that type use it automatically:

```python
import pandas as pd
from dash import dash_table
from dash_fn_interact import register_renderer

register_renderer(
    pd.DataFrame,
    lambda df: dash_table.DataTable(
        data=df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in df.columns],
    ),
)
```

Built-in renderers (checked in order):

1. Explicit `_render=` on `interact()`
2. Global registry (`register_renderer`)
3. `plotly.graph_objects.Figure` → `dcc.Graph`
4. Dash component → as-is
5. `str` → `dcc.Markdown`
6. `int` / `float` / `bool` → `html.P`
7. `pandas.DataFrame` → `DataTable`
8. `matplotlib.figure.Figure` → base64 PNG image
9. Fallback → `html.Pre(repr(result))`

## API Reference

### page

::: dash_interact.page.current

::: dash_interact.page.interact

::: dash_interact.page.add

::: dash_interact.page.run

### Page

::: dash_interact.page.Page

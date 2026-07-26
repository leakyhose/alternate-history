# Divergence

An alternate history simulator. Pick a starting point in history, type one "what if", and watch the next few decades play out on a world map.

![Quebec secedes, 1999](docs/images/quebec-1999.png)

![The same timeline five years later](docs/images/quebec-2004.png)

*"The 1995 Quebec referendum passes." The map redraws as the simulation runs, and the panel on the right fills in with events and quotes from the people involved.*

## What it does

Start from a scenario, type a divergence in plain English, and pick how many years to advance (5, 10, 25 or 50). One step returns a narrative of the period, updated rulers with generated portraits, quotes from the leaders involved, and territorial changes applied province by province on the map.

From there you can continue the same timeline, queue several steps at once, or type a new divergence to push it somewhere else. Every step is snapshotted, so the year slider scrubs the map back and forth and the timeline branches where you intervened.

![The present-day world map](docs/images/world-map.png)

## How it works

The backend is a [LangGraph](https://langchain-ai.github.io/langgraph/) graph of six Gemini agents. One pass through it is one step of history.

| Agent | Model | Job |
| --- | --- | --- |
| **Filter** | `gemini-2.5-flash-lite` | Rejects divergences that don't fit the scenario or its date range, and picks the starting year. |
| **Historian** | `gemini-2.5-flash-lite` | Reports what actually happened in the period. Kept blind to the alternate timeline so it stays a source of real history; extrapolates past the present day. |
| **Dreamer** | `gemini-3-flash-preview` | Makes the decisions. Turns real history plus accumulated divergences into a narrative, new rulers, and a structured list of territorial changes. |
| **Geographer** | `gemini-3-flash-preview` | Applies those changes to province ownership via tool calls. It never sees all 5,000 provinces at once: 924 named areas roll up into 95 regions, and it drills down from there. |
| **Quotegiver** | `gemini-2.5-flash-lite` | Writes in-character quotes from the rulers who mattered this step. |
| **Illustrator** | `gemini-2.5-flash-image` | Pixel-art portraits, cached and generated on a background thread pool. |

The frontend streams each stage over server-sent events, so the narrative and quotes appear while the map is still redrawing. Old steps get condensed into a running summary to keep the Dreamer's prompt from growing without limit.

![Generated quotes and portraits](docs/images/quotes.png)

The map is a WebGPU canvas. A 5632×2304 grid of province IDs is baked into two uint16 textures, and a compute shader recolours provinces by owner and draws borders on the GPU, which is what makes repainting thousands of provinces per step cheap.

## Scenarios

| Scenario | Range | Countries |
| --- | --- | --- |
| Collapse of Rome | 116-1453 | Rome, plus the eastern and western empires |
| Canada and the US | 1868-2025 | Canada, the US, Quebec, Federal States of America |
| Current Day | 2020-2025 | All 195, experimental |

Each one is a directory under `backend/static/scenarios/`: `metadata.json` for country tags, colours and date range, `provinces.json` and `rulers.json` keyed by year, and a logo. Adding a scenario needs no code changes.

## Running it

Needs Python 3.11+, Node 18+, a [Gemini API key](https://aistudio.google.com/apikey), and a WebGPU browser (Chrome or Edge).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=your_key_here" > .env
uvicorn main:app --reload
```

Run it from inside `backend/`; the data paths are relative to that directory. Then:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend defaults to `http://localhost:8000` for the API, override with `NEXT_PUBLIC_API_URL`.

## Layout

```
backend/
  agents/        one file per agent, each with its own prompt and schema
  workflows/     LangGraph wiring, shared state, node wrappers
  api/           FastAPI routes including the SSE streaming endpoints
  util/          province lookups, log condensing, portrait cache
  static/        regions.json, areas.json, scenarios/
frontend/
  src/components/        map canvas, timeline, panels
  src/lib/map-renderer/  WebGPU setup and viewport maths
  public/                WGSL shaders, baked province ID textures
```

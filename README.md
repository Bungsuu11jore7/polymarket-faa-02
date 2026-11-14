# Polymarket FAA Attribution Forecaster

Forecast Polymarket's FAA outage attribution prices minute by minute,
4 hours ahead: for every market and every minute after each checkpoint,
five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) of that minute's Yes price.

## Method

`main.py` is stdlib-only, offline and deterministic. For each market:

- **Volatility**: RMS of the 1-minute price changes over the last 120
  minutes, floored at 0.0002 and capped at 0.01 price units per minute.
  Quiet markets get narrow bands; jumpy markets get wide ones. The house
  baseline's fixed 0.0025 for every market is too wide for quiet markets
  and too narrow for jumpy ones.
- **Median**: the checkpoint price (persistence). Trend extrapolation and
  mean reversion toward the trailing mean were both tested and both made
  the backtest worse, so the median does not move.
- **Spread shape**: the spread grows as `h**0.35`, not `sqrt(h)`.
  Prices are sticky step functions, so long-horizon variance grows slower
  than a random walk (measured: alpha 0.50 scored 0.322, alpha 0.35
  scored 0.271).
- **Tails**: the 5% / 95% quantiles are widened x1.3, because jumps make
  the outer quantiles heavier-tailed than a normal.

Quantiles are normal z-scores of the scaled spread, clamped to [0, 1]
and rounded to 6 decimals, non-decreasing per row.

## Practice backtest (kit cases p00-p05, mean pinball loss x100)

| case | house baseline | this forecaster |
|------|---------------|-----------------|
| p00  | 0.536138      | 0.465122        |
| p01  | 0.380352      | 0.314610        |
| p02  | 0.408408      | 0.349952        |
| p03  | 0.368599      | 0.228878        |
| p04  | 0.298794      | 0.208283        |
| p05  | 0.238232      | 0.113975        |
| **overall** | **0.363589** | **0.269237** |

-26% vs the house baseline, better on every case. (The harness
reproduces the RULES.txt baseline of 0.363589 exactly, so the comparison
is on the same footing. The practice is cut from the NVIDIA CEO event,
not the FAA family, so its score is no guide to the final — but the
method is event-agnostic: it uses only each market's own recent prices.)

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `<id>.in` in the input directory, writes one `<id>.out`
per case. Runs in ~0.3s for all six practice cases; two runs are
byte-identical.

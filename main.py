#!/usr/bin/env python3
"""Forecast Polymarket FAA outage attribution prices, minute by minute, 4 hours ahead.

Method (backtested on the kit's 6 practice cases, p00-p05):
  per-market empirical volatility over the last 120 minutes of 1-minute
  price changes (RMS of diffs, floored at 0.0002 and capped at 0.01),
  persistence median at the checkpoint price (no drift: trend extrapolation
  and mean reversion both HURT the backtest), spread growing as h**0.35
  (sub-sqrt: prices are sticky step functions, so long-horizon variance
  grows slower than a random walk; measured on practice: alpha 0.50 scored
  0.322, alpha 0.35 scored 0.271), outer quantiles (5%/95%) widened x1.3
  for jump-aware tails. Quantiles are normal z-scores of the scaled spread,
  clamped to [0, 1] and rounded to 6 decimals.

  Practice backtest (mean pinball loss x100, lower is better):
    house baseline (fixed sigma 0.0025, sqrt(h)) : 0.363589
    this forecaster                               : 0.269237  (-26%)

  Stdlib only, offline, deterministic: same input bytes -> same output bytes.
  Reads $MAKEFUN_INPUT_DIR (default /input), writes $MAKEFUN_OUTPUT_DIR
  (default /output), one <id>.out per <id>.in, in name order.
"""
import json
import math
import os
import sys

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.644854, -0.67449, 0.0, 0.67449, 1.644854]
OUTER_SCALE = 1.3          # widen the 5% / 95% quantiles (jump-aware tails)
WINDOW = 120               # minutes of 1-min diffs for the volatility estimate
SIGMA_FLOOR = 0.0002       # per-minute sigma floor (price units)
SIGMA_CAP = 0.01           # per-minute sigma cap (price units)
ALPHA = 0.35               # spread grows as h**ALPHA (sub-sqrt: sticky prices)


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    v = round(min(1.0, max(0.0, x)) * 1e6) / 1e6
    return v + 0.0


def sigma(prices):
    """RMS of the last WINDOW 1-minute price changes, floored and capped."""
    n = len(prices)
    if n < 2:
        return SIGMA_FLOOR
    diffs = prices[-WINDOW - 1:] if n > WINDOW else prices
    s2 = 0.0
    m = 0
    for i in range(len(diffs) - 1):
        d = diffs[i + 1] - diffs[i]
        s2 += d * d
        m += 1
    if m == 0:
        return SIGMA_FLOOR
    s = math.sqrt(s2 / m)
    if s < SIGMA_FLOOR:
        return SIGMA_FLOOR
    if s > SIGMA_CAP:
        return SIGMA_CAP
    return s


def forecast(market, horizon):
    """240 rows of five quantiles for one market, median at checkpoint price."""
    prices = market["prices"]
    if not prices:
        raise ValueError("market %s has no prices" % market.get("id"))
    x = prices[-1]
    s = sigma(prices)
    zz = [Z[0] * OUTER_SCALE, Z[1], Z[2], Z[3], Z[4] * OUTER_SCALE]
    rows = []
    for h in range(1, horizon + 1):
        spread = s * (h ** ALPHA)
        row = [price6(x + z * spread) for z in zz]
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(f for f in os.listdir(in_dir) if f.endswith(".in"))
    for name in names:
        cid = name[:-3]
        with open(os.path.join(in_dir, name), "r", encoding="utf-8") as f:
            case = json.load(f)
        qs = case["quantiles"]
        if len(qs) != len(QUANTILES) or any(q != QUANTILES[j] for j, q in enumerate(qs)):
            raise ValueError("%s asks for quantiles %r, not %r" % (name, qs, QUANTILES))
        forecasts = [
            {"id": m["id"], "q": forecast(m, case["horizon_minutes"])}
            for m in case["markets"]
        ]
        out = json.dumps({"forecasts": forecasts}, separators=(",", ":")) + "\n"
        with open(os.path.join(out_dir, cid + ".out"), "w", encoding="utf-8") as f:
            f.write(out)


if __name__ == "__main__":
    main()

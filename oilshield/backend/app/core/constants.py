"""Documented model constants for the OilShield deterministic core.

Every constant here feeds a *pure, deterministic* formula in the scenario
impact cascade, the procurement recommendation score, or the risk band
classifier. They are illustrative demo defaults chosen to sit inside the
ranges documented in the design, not calibrated forecasts. Because the core
math is deterministic, these values fully determine the numbers a judge sees,
so they are centralized here and referenced by the services rather than being
scattered as magic numbers.

References:
- Scenario impact cascade  -> design.md "Scenario impact computation"
- Procurement scoring       -> design.md "Procurement Recommendation_Score formula"
- Risk banding              -> design.md Property 8 / Requirement 3.4

Requirements: 3.4, 6.2, 8.2, 8.3
"""

from typing import Final

# ---------------------------------------------------------------------------
# Scenario impact cascade constants
# ---------------------------------------------------------------------------
# The cascade turns a scenario's assumptions into a per-day timeline via:
#
#   supply_loss_fraction = clamp(
#       corridor_import_share * (corridor_closure_pct / 100)
#         + production_cut_kbd / TOTAL_IMPORT_KBD,
#       0, 1)
#   refinery_run_rate_pct(day) = clamp(100 - K_REF * supply_loss_fraction * 100, 0, 100)
#   fuel_price_index(day)      = 100 * (1 + K_PRICE * supply_loss_fraction)
#   spr_days_of_cover(day)     = max(0, spr_start_days - day * supply_loss_fraction / DRAWDOWN_DIVISOR)
#   gdp_index(day)             = 100 * (1 - K_GDP * supply_loss_fraction * (day / duration_days))
#
# All coefficients are non-negative so the documented monotonicity properties
# (higher closure never raises SPR cover, etc.) hold by construction.

# Total crude India imports, in thousand barrels/day (kbd). Used to convert an
# absolute OPEC+ production cut into a fraction of national supply. India's
# crude imports sit around 4.5-5.0 million bbl/day; 5000 kbd is a round,
# representative figure.
TOTAL_IMPORT_KBD: Final[float] = 5000.0

# Refinery sensitivity: fraction of a supply shock that passes through to
# reduced refinery run rate. At K_REF = 0.8 a total supply loss drives run rate
# down by 80 points (to ~20%), reflecting partial compensation from inventories
# and alternate feedstock. Range kept in [0, 1] so run rate stays clampable.
K_REF: Final[float] = 0.8

# Fuel price sensitivity: proportional price rise per unit of supply loss.
# At K_PRICE = 1.5 a 10% supply loss lifts the fuel price index by ~15%.
K_PRICE: Final[float] = 1.5

# GDP sensitivity: proportional GDP drag per unit of supply loss, accrued
# linearly across the scenario horizon. At K_GDP = 0.5 a sustained 10% supply
# loss trims the GDP index by ~5% by the end of the scenario.
K_GDP: Final[float] = 0.5

# SPR drawdown divisor: scales how quickly the Strategic Petroleum Reserve
# days-of-cover is consumed. Larger => slower drawdown. At 2.0, a 50% supply
# loss burns ~0.25 days of cover per elapsed day.
DRAWDOWN_DIVISOR: Final[float] = 2.0

# ---------------------------------------------------------------------------
# Procurement recommendation-score constants
# ---------------------------------------------------------------------------
# recommendation_score = 100 * (
#       W_PRICE   * price_score
#     + W_AVAIL   * avail_score
#     + W_CONGEST * congest_score
#     + W_COMPAT  * compat_score )
# where price_score = clamp((PRICE_CEILING - spot_price) / (PRICE_CEILING - PRICE_FLOOR), 0, 1).
# Weights are non-negative and sum to 1 so the score stays in [0, 100] and is
# monotone in each attribute (Property 18).

W_PRICE: Final[float] = 0.35     # weight on (normalized) spot price attractiveness
W_AVAIL: Final[float] = 0.20     # weight on tanker availability
W_CONGEST: Final[float] = 0.15   # weight on port congestion (inverted to a score)
W_COMPAT: Final[float] = 0.30    # weight on crude-grade compatibility

# Sanity check: the four weights must sum to 1 so the score scales cleanly to
# [0, 100]. Enforced at import time to catch accidental edits.
assert abs((W_PRICE + W_AVAIL + W_CONGEST + W_COMPAT) - 1.0) < 1e-9, (
    "Procurement weights must sum to 1.0"
)

# Spot-price normalization bounds, in USD per barrel. A price at or below the
# floor scores 1.0 (best); at or above the ceiling scores 0.0 (worst). Bounds
# bracket a realistic crude trading band.
PRICE_FLOOR: Final[float] = 40.0
PRICE_CEILING: Final[float] = 120.0

# Minimum grade compatibility (0..1) an option must meet to be recommended.
# Options below this are dropped before ranking (Requirement 8.3).
MIN_COMPAT: Final[float] = 0.4

# ---------------------------------------------------------------------------
# Risk band thresholds
# ---------------------------------------------------------------------------
# A risk score in [0, 100] is banded as:
#   low       : 0  <= score <= 33
#   elevated  : 34 <= score <= 66
#   high       : 67 <= score <= 100
# The classifier uses the two upper bounds below; anything above
# RISK_BAND_ELEVATED_MAX is "high". These are the inclusive maxima for each
# lower band, so banding is total over [0, 100] with no gaps or overlaps
# (Property 8 / Requirement 3.4).
RISK_BAND_LOW_MAX: Final[float] = 33.0
RISK_BAND_ELEVATED_MAX: Final[float] = 66.0

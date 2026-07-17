# Monte Carlo Portfolio Simulation

## Purpose

MicroScore uses Monte Carlo simulation to describe uncertainty around a scored
portfolio and a threshold policy. It does **not** randomize an individual
borrower's score, produce a new credit score, or turn simulated profit into an
automatic lending decision.

The simulation answers a narrower planning question:

> If an MFI applies one review policy to the currently scored portfolio, what
> range of approvals, defaults, exposure, and financial outcomes could occur
> under baseline and stressed assumptions?

This belongs in the MFI Policy Lab because the deterministic policy table shows
one action mix, while Monte Carlo shows how uncertain portfolio outcomes remain
after that policy is chosen.

## Simulation Unit

Each scored application contributes:

- stored high-risk probability `p_i`;
- requested loan amount;
- deterministic threshold-policy action: approve, manual review, or decline.

Unscored applications are excluded and reported in the response. The endpoint
uses the same organization scope as the MFI application queue, so an analyst
cannot simulate another MFI's portfolio.

## Probability Model

For application `i`, iteration `k`, and stress scenario `s`, the simulated
default probability is:

```text
logit(p_i,s,k) = logit(p_i)
                 + scenario_log_odds_shift_s
                 + macro_volatility * Z_k
                 + calibration_volatility * epsilon_i,k
```

where:

- `Z_k` is one shared standard-normal shock for the whole portfolio, creating
  correlated movement across borrowers;
- `epsilon_i,k` is an application-level standard-normal calibration shock;
- baseline, adverse, and severe scenarios add progressively larger log-odds
  shifts;
- probabilities are clipped before the logit transform for numerical safety.

This is a transparent one-factor uncertainty model, not a fitted macroeconomic
credit model.

## Review And Default Draws

- Auto-approved applications enter the simulated book in every iteration.
- Applications in the manual-review band enter with the configured review
  approval rate.
- Auto-declined applications do not enter the simulated book.
- Each entered loan defaults when a uniform draw is below its stressed default
  probability.

All stress scenarios reuse common random numbers within a run. This paired
design reduces simulation noise when comparing baseline, adverse, and severe
results: a worse scenario changes the risk assumption, not the random sample.

## Financial Outcome

For an approved loan amount `A`:

```text
non-default outcome = A * interest_margin_rate - operating_cost
default outcome     = -A * loss_given_default - operating_cost
```

The portfolio result is the sum across simulated approved loans. This is a
simple one-period contribution model. It does not include funding costs,
prepayment, collections timing, taxes, capital charges, or multi-period cash
flows.

The default operating cost is zero because current synthetic and local demo
amounts do not share a validated currency scale. A zero-cost run carries an
explicit warning. Before interpretation, the analyst should enter a cost in the
same amount units as the application portfolio; the UI deliberately says
`units` rather than claiming calibrated KZT.

The monetary interpretation boundary is formalized in
[KZT_CALIBRATION_ASSUMPTIONS.md](KZT_CALIBRATION_ASSUMPTIONS.md). Until the
project has consented local repayment outcomes and documented KZT principal,
income, margin, LGD, cost, and tenor evidence, Monte Carlo amount outputs remain
prototype amount units.

## Reported Outputs

For each stress scenario, the API reports:

- mean and 5th/50th/95th percentiles for approved count;
- mean and percentile range for defaults and default rate;
- mean and percentile range for approved exposure;
- mean and percentile range for portfolio result;
- probability of a negative portfolio result;
- mean stressed default probability;
- downside at the 5th percentile;
- Monte Carlo standard errors for mean portfolio result, mean default count,
  and estimated loss probability.

The response also echoes every assumption, the seed, iteration count, policy,
portfolio size, model versions present in the score snapshots, and a warning
that the result is scenario planning only.

The API also warns when unscored applications were excluded, multiple score
versions are mixed, or stored scores do not match the currently active model.
The run remains available for diagnosis, but those warnings should be resolved
before comparing a policy for operational use.

## Reproducibility

Runs are deterministic for the same:

- scored portfolio;
- model score snapshots;
- policy;
- assumptions;
- iteration count;
- random seed.

The API accepts 100 to 20,000 iterations. The default is 5,000. A fixed seed is
useful for review and tests; changing the seed is useful for stability checks.
To protect the synchronous prototype API, a run is limited to 20 million
scored-application × iteration cells. Larger portfolios must reduce iterations
or move simulation to a background worker.

The standard errors describe finite-simulation noise, not model or economic
uncertainty. They should shrink as iterations increase. A small Monte Carlo
standard error does not make unvalidated probabilities or assumptions accurate.

Before simulation, the API builds a canonical, application-ID-sorted snapshot
of each usable application's amount, probability, model version, and scoring
timestamp. Its SHA-256 `portfolio_fingerprint` makes it possible to distinguish
a repeated run on the same score snapshot from a run after the portfolio or its
scores changed.

Every successful local API run is stored as an immutable SQLite record containing
the request, full result, actor, organization scope, timestamp, and fingerprint.
`GET /mfi/simulations` returns compact history and
`GET /mfi/simulations/{simulation_id}` restores the exact saved result. Analysts
can only access their organization; administrators retain global visibility.

## Interpretation Boundaries

Current synthetic probabilities are not calibrated on real MFI repayment
outcomes. Therefore:

- output amount-unit values are demonstrations, not forecasts;
- `probability_of_loss` is conditional on user-supplied assumptions;
- scenario shifts are transparent stress assumptions, not econometric
  estimates for Kazakhstan;
- percentile ranges do not represent regulatory VaR or required capital;
- Monte Carlo cannot repair biased features, weak calibration, or missing
  outcome data;
- analyst and governance review remain mandatory.

Before pilot use, the MFI must replace default assumptions with documented
funding, margin, LGD, operating-cost, review-conversion, calibration, and stress
evidence from consented local data.

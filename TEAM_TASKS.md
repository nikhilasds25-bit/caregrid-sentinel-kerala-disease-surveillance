# CareGrid Sentinel — Open Team Development Tasks

Task ownership is intentionally unassigned. The team should decide owners, priorities, and acceptance criteria together. All work should preserve source provenance and keep experimental results separate from operational surveillance until independently reviewed.

## 1. Historical data and source validation

- Re-review official dashboard JSON structure and source-native category meanings for every year, including unavailable categories versus explicit zero values.
- Seek official DHS monthly/district-month reports and document exact category definitions, temporal semantics, coverage, and reproducible retrieval.
- Resolve or document the four dashboard district-to-state mismatch cells and DHS/dashboard differences; never silently replace source observations.
- Confirm district identifiers, reporting calendars, deaths/cases semantics, revisions, missing periods, and duplicates.
- Assess whether the historical Confirmed series is stable enough for any pooled analysis. Keep Suspected and DHS Probable separate unless source evidence establishes equivalence.
- Review weather coordinate mapping, raw Open-Meteo responses, missingness, units, and representativeness. Investigate district gridded/areal weather and weather forecasts available at historical forecast origins.
- If population rates or district spatial models are considered, source vetted year-specific population and boundary inputs rather than estimating or weighting without evidence.

## 2. Bayesian probabilistic modelling

- Establish an approved inference environment and reproducible dependency specification before choosing a sampler.
- Pilot Bayesian Poisson and Bayesian Negative Binomial specifications with regularizing priors and a small, well-documented feature set.
- Define district partial-pooling structure and assess identifiability and prior sensitivity.
- Require multiple chains, R-hat, effective sample sizes, divergences, prior/posterior predictive checks, and sampling-resource reporting.
- Compare posterior predictive forecasts against existing matched chronological baselines. Do not equate fixed-effect NB2 with a Bayesian model.

## 3. Gaussian Process and Student-t Process experiments

- Define candidate kernels, seasonal/trend structure, count observation likelihood or transformation, and uncertainty interpretation before implementation.
- Evaluate whether the 14-district panel is sufficient for the proposed covariance structure and computational cost.
- Test stability and predictive calibration in chronological folds; document where Gaussian and Student-t assumptions do or do not fit count outcomes.
- Keep any model that fails numerical or posterior/predictive diagnostics marked unavailable or not evaluable.

## 4. Outbreak detection and probability

- Engage epidemiological reviewers to define the target event and any threshold using independent source documentation.
- Assemble independently reviewed outbreak/event labels with dates, geography, adjudication process, and provenance.
- Keep retrospective unusual-activity detection separate from future count forecasting and from threshold-exceedance probability.
- Evaluate anomaly methods against labeled events using sensitivity, specificity, precision-recall, false alerts per district-year, and lead time where event dates support it.
- Evaluate probabilistic outbreak estimates with Brier score, log loss, reliability diagrams/calibration, and temporal/geographic holdouts.
- Do not issue operational alerts or infer official thresholds until event definitions and validation are approved.

## 5. Uncertainty calibration

- Investigate strong undercoverage in saved rolling-origin intervals, particularly long-horizon Dengue and Poisson configurations.
- Break interval diagnostics down by disease, district, horizon, forecast origin, count range, and years with potential source changes.
- Review unusually broad overcovering intervals as well as narrow undercovering intervals; report both coverage and proper interval scores.
- Test calibration adjustments only within nested chronological development folds; preserve the 2025 evaluation as an untouched holdout.
- Obtain more temporal validation origins and, if feasible, an independent prospective period before claiming calibration.
- Distinguish predictive intervals for future counts from confidence intervals for parameters or means in all user-facing materials.

## 6. Model evaluation and selection

- Independently review metric definitions, comparable observation alignment, selection gates, composite weights, and minimum evidence thresholds.
- Test sensitivity of selected/insufficient-evidence outcomes to policy choices without selecting policy based on the final holdout.
- Add paired uncertainty estimates for model score differences only with a defensible temporal/geographic resampling design.
- Expand task-specific evaluation: count log scores and interval scores for forecasting; labeled-event metrics for anomaly detection; Brier/log loss and calibration for outbreak probability.
- Version and hash every input, feature set, model implementation, selection policy, validation design, and output.
- Keep `insufficient_evidence` as a valid outcome; do not make a forced winner the default.

## 7. Dashboard integration

- Do not integrate current experimental selections as default/live models.
- First agree on an API contract that distinguishes observed reports, retrospective predictions, future forecasts, uncertainty, source status, and model readiness.
- Design explicit exploratory labels, prediction-origin/date ranges, uncertainty displays, data caveats, and accessible comparisons before exposing model outputs.
- Keep failed, unavailable, and not-evaluable states visible; avoid success-shaped fallbacks or implying alerts are validated.
- Integrate only after source, model, uncertainty, and clinical/epidemiological review gates pass.
- Continue to show that hospital-capacity values are hypothetical unless a verified official capacity feed is acquired and validated.

## 8. Packaging, reproducibility, and collaboration

- Establish a Git baseline and remote collaboratively; the current local repository has no commits or remotes and files are untracked.
- Agree on Python and Node versions, pin or constrain dependencies, and add clean Windows setup verification.
- Re-run tests and builds from a fresh extraction/environment; record platform/version details.
- Preserve source snapshots, retrieval metadata, hashes, candidate metadata, and discrepancy reports with any derived dataset.
- Avoid committing credentials, local environments, caches, or mutable generated artifacts unless the team explicitly versions them.

## Suggested sequencing

1. Source/classification review and collaborative Git baseline.
2. Clean-environment reproducibility and uncertainty diagnostics.
3. Bayesian pilot with posterior checks, if dependencies and data review support it.
4. Obtain outbreak thresholds and independent event labels before anomaly/outbreak evaluation.
5. Revisit model selection and any dashboard integration only after evidence gates are met.

# Hospital Capacity Simulation

## Overview

CareGrid Sentinel includes an interactive, hypothetical hospital capacity
simulation tool.

It allows users to explore how assumed disease cases, hospitalization rates,
patient admissions, and lengths of stay may affect an assumed number of
hospital beds.

The simulator is intended for educational and exploratory scenario analysis.

It is not connected to verified hospital admission, discharge, bed-capacity,
or occupancy datasets.

## 1. Hospital Demand Estimation

The disease-based scenario accepts:

- Hypothetical disease cases
- User-defined hospitalization rate (%)

Estimated admissions are calculated as:

Estimated admissions = ceil(Disease cases × Hospitalization rate / 100)

The ceiling function rounds fractional admission estimates upward.

Example:

Disease cases = 500
Hospitalization rate = 20%

Estimated admissions = 100

This calculation is based entirely on user-defined assumptions. The
hospitalization rate is not calibrated to a disease-specific clinical dataset.

## 2. Immediate-Demand Capacity Simulation

The simulator accepts:

- Total hypothetical hospital beds
- Initially occupied beds
- Additional hypothetical patients

The additional patient count can be entered manually or calculated using
the disease-based scenario.

Calculations:

Projected occupied beds = Initially occupied beds + Additional patients

Occupancy percentage = (Projected occupied beds / Total beds) × 100

Remaining beds = max(0, Total beds - Projected occupied beds)

Hypothetical bed shortage = max(0, Projected occupied beds - Total beds)

Capacity status:

- Within capacity: Projected occupied beds < Total beds
- At capacity: Projected occupied beds = Total beds
- Over capacity: Projected occupied beds > Total beds

The immediate-demand calculation assumes all additional patients require
beds simultaneously.

## 3. Length-of-Stay Simulation

The time-based simulation accepts:

- Estimated additional admissions
- Total hypothetical beds
- Initially occupied beds
- Admission period in days
- Assumed length of stay in days

Additional admissions are distributed as evenly as possible across the
admission period. When division leaves a remainder, earlier days receive
one additional admission.

Each additional patient is assumed to stay for exactly the specified
number of days.

A patient admitted on day 1 with a three-day stay occupies a bed on
days 1, 2, and 3 and is discharged at the start of day 4.

Daily occupied beds are calculated as:

Daily occupied beds =
Initially occupied beds + Active additional patients

The simulation tracks:

- Daily additional admissions
- Daily additional discharges
- Daily occupied beds
- Daily remaining beds
- Daily hypothetical bed shortages
- Peak occupied beds
- Peak occupancy percentage
- Peak hypothetical bed shortage

Important modelling assumptions:

- Admissions are approximately evenly distributed.
- All additional patients have the same fixed length of stay.
- Initially occupied beds remain occupied throughout the simulation.
- No discharges are modelled for patients occupying beds initially.
- No distinction is made between hospital departments or bed types.
- No patient transfers, mortality, or readmissions are modelled.
- The displayed horizon ends on the final day of occupancy for the last
  admission; it does not display the final discharge event afterward.

The model is deterministic and does not quantify uncertainty.

## 4. Preparedness Planning

Preparedness planning evaluates hypothetical capacity pressure.

When valid length-of-stay inputs are available, it uses the peak occupied
beds from that simulation.

Otherwise, it uses the immediate-demand calculation.

The three scenario categories are:

- Within capacity
- At capacity
- Over capacity

The dashboard presents rule-based considerations for exploring alternative
assumptions, such as hospitalization rates, admission periods, lengths of
stay, and hypothetical bed capacity.

These considerations are not clinical guidance, staffing instructions,
operational alerts, or recommendations for actual hospital decisions.

## 5. Dashboard Features

The React dashboard provides:

- Manual and disease-based simulation modes
- Hypothetical disease-case and hospitalization-rate inputs
- Bed-capacity and occupancy inputs
- Immediate-demand occupancy indicators
- Remaining-bed and hypothetical-shortage calculations
- Length-of-stay inputs
- Daily occupancy visualization
- Peak occupancy and shortage indicators
- Rule-based preparedness considerations
- Input validation and explanatory disclaimers

The occupancy gauge uses:

- Green: within capacity
- Amber: at capacity
- Red: over capacity

All hospital simulation inputs are user-defined.

## 6. Validation

Frontend testing uses Vitest.

The verified test suite includes:

- Capacity calculation unit tests
- Length-of-stay calculation unit tests
- Preparedness planning unit tests
- React dashboard interaction tests
- Existing dashboard regression tests

The latest completed frontend verification reported:

- 31 tests passed
- 8 test files passed
- TypeScript compilation passed
- Vite production build passed

Manual browser checks confirmed the displayed results for example manual
and disease-based scenarios, including the length-of-stay chart and the
red over-capacity gauge.

Backend regression testing should be completed separately before merging.

## 7. Limitations

The simulator does not use verified real-time hospital data.

In particular:

- Hospital bed counts are not sourced from healthcare facilities.
- Existing occupancy is entered manually.
- Disease-related admission rates are assumptions.
- Length of stay is fixed rather than a statistical distribution.
- Existing patients do not leave during the modelled period.
- Admissions are distributed evenly rather than forecast dynamically.
- Hospital-specific resources and service constraints are not represented.
- Outputs have not been validated against observed hospital admissions.
- No clinical or operational preparedness recommendations are generated.

Disease surveillance data and retrospective forecasting results elsewhere
in CareGrid Sentinel must not be treated as validated future hospital
admission forecasts.

## 8. Reproducibility

From the repository root:

cd dashboard
npm test
npm run build

The simulator implementation is contained in:

- dashboard/src/capacitySimulation.ts
- dashboard/src/lengthOfStaySimulation.ts
- dashboard/src/preparednessPlanning.ts
- dashboard/src/App.tsx
- dashboard/src/styles.css

Associated tests are located in dashboard/src.

## 9. Intended Use

This feature demonstrates how hypothetical disease-related demand can be
translated into illustrative bed occupancy and capacity-pressure scenarios.

It is suitable for exploratory analysis, demonstrations, and educational
discussion.

It must not be used independently to make real hospital capacity,
admission, transfer, or clinical decisions.

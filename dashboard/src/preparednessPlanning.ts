export interface PreparednessScenario {
  totalBeds: number;
  peakOccupiedBeds: number;
  peakBedShortage: number;
}

export interface PreparednessResult {
  status: "within_capacity" | "at_capacity" | "over_capacity";
  title: string;
  considerations: string[];
}

export function assessPreparedness(
  scenario: PreparednessScenario,
): PreparednessResult {
  const { totalBeds, peakOccupiedBeds, peakBedShortage } = scenario;

  if (
    !Number.isSafeInteger(totalBeds) ||
    totalBeds <= 0 ||
    !Number.isSafeInteger(peakOccupiedBeds) ||
    peakOccupiedBeds < 0 ||
    !Number.isSafeInteger(peakBedShortage) ||
    peakBedShortage !== Math.max(0, peakOccupiedBeds - totalBeds)
  ) {
    throw new Error("Invalid preparedness scenario inputs.");
  }

  if (peakOccupiedBeds > totalBeds) {
    return {
      status: "over_capacity",
      title: "Hypothetical demand exceeds capacity",
      considerations: [
        "Explore scenarios with additional hypothetical bed capacity.",
        "Compare different admission periods and lengths of stay.",
        "Review how changes in the assumed demand affect peak occupancy.",
      ],
    };
  }

  if (peakOccupiedBeds === totalBeds) {
    return {
      status: "at_capacity",
      title: "Hypothetical demand reaches capacity",
      considerations: [
        "Examine alternative assumptions for admissions and discharges.",
        "Explore whether additional hypothetical reserve capacity changes the result.",
      ],
    };
  }

  return {
    status: "within_capacity",
    title: "Hypothetical demand remains within capacity",
    considerations: [
      "Compare alternative disease-case and hospitalization-rate assumptions.",
      "Review whether longer hypothetical stays increase peak occupancy.",
    ],
  };
}

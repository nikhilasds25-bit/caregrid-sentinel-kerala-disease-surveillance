export interface CapacityScenario {
  diseaseCases: number;
  hospitalizationRate: number;
  totalBeds: number;
  occupiedBeds: number;
}

export interface CapacityResult {
  estimatedAdmissions: number;
  projectedOccupiedBeds: number;
  occupancyPercent: number;
  remainingBeds: number;
  bedShortage: number;
  stressLevel: "within_capacity" | "at_capacity" | "over_capacity";
}

export function simulateCapacity(
  scenario: CapacityScenario,
): CapacityResult {
  const {
    diseaseCases,
    hospitalizationRate,
    totalBeds,
    occupiedBeds,
  } = scenario;

  if (
    !Number.isInteger(diseaseCases) ||
    diseaseCases < 0 ||
    !Number.isFinite(hospitalizationRate) ||
    hospitalizationRate < 0 ||
    hospitalizationRate > 100 ||
    !Number.isInteger(totalBeds) ||
    totalBeds <= 0 ||
    !Number.isInteger(occupiedBeds) ||
    occupiedBeds < 0 ||
    occupiedBeds > totalBeds
  ) {
    throw new Error("Invalid hospital capacity scenario inputs.");
  }

  const estimatedAdmissions = Math.ceil(
    diseaseCases * (hospitalizationRate / 100),
  );

  const projectedOccupiedBeds = occupiedBeds + estimatedAdmissions;

  const occupancyPercent =
    (projectedOccupiedBeds / totalBeds) * 100;

  const remainingBeds = Math.max(
    0,
    totalBeds - projectedOccupiedBeds,
  );

  const bedShortage = Math.max(
    0,
    projectedOccupiedBeds - totalBeds,
  );

  const stressLevel =
    projectedOccupiedBeds > totalBeds
      ? "over_capacity"
      : projectedOccupiedBeds === totalBeds
        ? "at_capacity"
        : "within_capacity";

  return {
    estimatedAdmissions,
    projectedOccupiedBeds,
    occupancyPercent,
    remainingBeds,
    bedShortage,
    stressLevel,
  };
}

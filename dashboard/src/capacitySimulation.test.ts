import { describe, expect, it } from "vitest";
import { simulateCapacity } from "./capacitySimulation";

describe("hypothetical hospital capacity simulation", () => {
  it("estimates admissions and detects a bed shortage", () => {
    const result = simulateCapacity({
      diseaseCases: 500,
      hospitalizationRate: 20,
      totalBeds: 100,
      occupiedBeds: 40,
    });

    expect(result).toEqual({
      estimatedAdmissions: 100,
      projectedOccupiedBeds: 140,
      occupancyPercent: 140,
      remainingBeds: 0,
      bedShortage: 40,
      stressLevel: "over_capacity",
    });
  });

  it("identifies a scenario within capacity", () => {
    const result = simulateCapacity({
      diseaseCases: 100,
      hospitalizationRate: 10,
      totalBeds: 100,
      occupiedBeds: 50,
    });

    expect(result.estimatedAdmissions).toBe(10);
    expect(result.projectedOccupiedBeds).toBe(60);
    expect(result.occupancyPercent).toBe(60);
    expect(result.remainingBeds).toBe(40);
    expect(result.bedShortage).toBe(0);
    expect(result.stressLevel).toBe("within_capacity");
  });

  it("identifies a scenario exactly at capacity", () => {
    const result = simulateCapacity({
      diseaseCases: 100,
      hospitalizationRate: 20,
      totalBeds: 100,
      occupiedBeds: 80,
    });

    expect(result.projectedOccupiedBeds).toBe(100);
    expect(result.stressLevel).toBe("at_capacity");
  });

  it("rounds estimated admissions up to whole patients", () => {
    const result = simulateCapacity({
      diseaseCases: 13,
      hospitalizationRate: 10,
      totalBeds: 20,
      occupiedBeds: 0,
    });

    expect(result.estimatedAdmissions).toBe(2);
  });

  it("rejects invalid hospitalization rates", () => {
    expect(() =>
      simulateCapacity({
        diseaseCases: 100,
        hospitalizationRate: 120,
        totalBeds: 100,
        occupiedBeds: 20,
      }),
    ).toThrow("Invalid hospital capacity scenario inputs.");
  });

  it("rejects existing occupancy greater than capacity", () => {
    expect(() =>
      simulateCapacity({
        diseaseCases: 100,
        hospitalizationRate: 10,
        totalBeds: 100,
        occupiedBeds: 120,
      }),
    ).toThrow("Invalid hospital capacity scenario inputs.");
  });

  it("rejects negative disease cases", () => {
    expect(() =>
      simulateCapacity({
        diseaseCases: -10,
        hospitalizationRate: 10,
        totalBeds: 100,
        occupiedBeds: 20,
      }),
    ).toThrow("Invalid hospital capacity scenario inputs.");
  });
});

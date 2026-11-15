import { describe, expect, it } from "vitest";
import { assessPreparedness } from "./preparednessPlanning";

describe("hypothetical preparedness planning", () => {
  it("identifies a scenario within capacity", () => {
    const result = assessPreparedness({
      totalBeds: 100,
      peakOccupiedBeds: 60,
      peakBedShortage: 0,
    });

    expect(result.status).toBe("within_capacity");
    expect(result.title).toContain("within capacity");
    expect(result.considerations.length).toBeGreaterThan(0);
  });

  it("identifies a scenario exactly at capacity", () => {
    const result = assessPreparedness({
      totalBeds: 100,
      peakOccupiedBeds: 100,
      peakBedShortage: 0,
    });

    expect(result.status).toBe("at_capacity");
    expect(result.title).toContain("reaches capacity");
  });

  it("identifies a scenario exceeding capacity", () => {
    const result = assessPreparedness({
      totalBeds: 100,
      peakOccupiedBeds: 140,
      peakBedShortage: 40,
    });

    expect(result.status).toBe("over_capacity");
    expect(result.title).toContain("exceeds capacity");
    expect(result.considerations.length).toBeGreaterThan(0);
  });

  it("rejects inconsistent bed-shortage calculations", () => {
    expect(() =>
      assessPreparedness({
        totalBeds: 100,
        peakOccupiedBeds: 140,
        peakBedShortage: 10,
      }),
    ).toThrow("Invalid preparedness scenario inputs.");
  });

  it("rejects invalid bed capacity", () => {
    expect(() =>
      assessPreparedness({
        totalBeds: 0,
        peakOccupiedBeds: 10,
        peakBedShortage: 10,
      }),
    ).toThrow("Invalid preparedness scenario inputs.");
  });
});

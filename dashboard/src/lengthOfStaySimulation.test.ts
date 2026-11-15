import { describe, expect, it } from "vitest";
import { simulateLengthOfStay } from "./lengthOfStaySimulation";

describe("hypothetical length-of-stay simulation", () => {
  it("distributes admissions across multiple days", () => {
    const result = simulateLengthOfStay({
      estimatedAdmissions: 10,
      totalBeds: 20,
      initiallyOccupiedBeds: 5,
      admissionPeriodDays: 5,
      lengthOfStayDays: 3,
    });

    expect(result.daily.slice(0, 5).map((row) => row.admissions))
      .toEqual([2, 2, 2, 2, 2]);

    expect(result.peakOccupiedBeds).toBe(11);
    expect(result.peakBedShortage).toBe(0);
  });

  it("models discharges after the assumed length of stay", () => {
    const result = simulateLengthOfStay({
      estimatedAdmissions: 6,
      totalBeds: 20,
      initiallyOccupiedBeds: 0,
      admissionPeriodDays: 3,
      lengthOfStayDays: 2,
    });

    expect(result.daily[0].occupiedBeds).toBe(2);
    expect(result.daily[1].occupiedBeds).toBe(4);
    expect(result.daily[2].discharges).toBe(2);
    expect(result.daily[2].occupiedBeds).toBe(4);
    expect(result.daily[3].discharges).toBe(2);
  });

  it("calculates peak occupancy and bed shortages", () => {
    const result = simulateLengthOfStay({
      estimatedAdmissions: 20,
      totalBeds: 10,
      initiallyOccupiedBeds: 5,
      admissionPeriodDays: 2,
      lengthOfStayDays: 3,
    });

    expect(result.peakOccupiedBeds).toBe(25);
    expect(result.peakBedShortage).toBe(15);
    expect(result.peakOccupancyPercent).toBe(250);
  });

  it("preserves initial occupancy when there are no admissions", () => {
    const result = simulateLengthOfStay({
      estimatedAdmissions: 0,
      totalBeds: 100,
      initiallyOccupiedBeds: 40,
      admissionPeriodDays: 5,
      lengthOfStayDays: 3,
    });

    expect(result.peakOccupiedBeds).toBe(40);
    expect(result.peakBedShortage).toBe(0);
    expect(result.daily.every((row) => row.occupiedBeds === 40)).toBe(true);
  });

  it("rejects invalid scenario assumptions", () => {
    expect(() =>
      simulateLengthOfStay({
        estimatedAdmissions: 10,
        totalBeds: 100,
        initiallyOccupiedBeds: 20,
        admissionPeriodDays: 0,
        lengthOfStayDays: 3,
      }),
    ).toThrow("Invalid length-of-stay scenario inputs.");
  });
});

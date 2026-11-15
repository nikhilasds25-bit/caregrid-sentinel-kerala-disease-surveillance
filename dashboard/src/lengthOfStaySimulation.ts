export interface StayScenario {
  estimatedAdmissions: number;
  totalBeds: number;
  initiallyOccupiedBeds: number;
  admissionPeriodDays: number;
  lengthOfStayDays: number;
}

export interface DailyCapacity {
  day: number;
  admissions: number;
  discharges: number;
  occupiedBeds: number;
  remainingBeds: number;
  bedShortage: number;
}

export interface StayResult {
  daily: DailyCapacity[];
  peakOccupiedBeds: number;
  peakBedShortage: number;
  peakOccupancyPercent: number;
}

export function simulateLengthOfStay(
  scenario: StayScenario,
): StayResult {
  const {
    estimatedAdmissions,
    totalBeds,
    initiallyOccupiedBeds,
    admissionPeriodDays,
    lengthOfStayDays,
  } = scenario;

  if (
    !Number.isSafeInteger(estimatedAdmissions) ||
    estimatedAdmissions < 0 ||
    !Number.isSafeInteger(totalBeds) ||
    totalBeds <= 0 ||
    !Number.isSafeInteger(initiallyOccupiedBeds) ||
    initiallyOccupiedBeds < 0 ||
    initiallyOccupiedBeds > totalBeds ||
    !Number.isInteger(admissionPeriodDays) ||
    admissionPeriodDays < 1 ||
    admissionPeriodDays > 365 ||
    !Number.isInteger(lengthOfStayDays) ||
    lengthOfStayDays < 1 ||
    lengthOfStayDays > 365
  ) {
    throw new Error("Invalid length-of-stay scenario inputs.");
  }

  const horizon = admissionPeriodDays + lengthOfStayDays - 1;

  const dailyAdmissions = Array(horizon).fill(0) as number[];
  const dailyDischarges = Array(horizon).fill(0) as number[];

  const baseAdmissions = Math.floor(
    estimatedAdmissions / admissionPeriodDays,
  );

  const extraAdmissions = estimatedAdmissions % admissionPeriodDays;

  for (let day = 0; day < admissionPeriodDays; day++) {
    const admissions =
      baseAdmissions + (day < extraAdmissions ? 1 : 0);

    dailyAdmissions[day] = admissions;

    const dischargeDay = day + lengthOfStayDays;

    if (dischargeDay < horizon) {
      dailyDischarges[dischargeDay] += admissions;
    }
  }

  let activePatients = 0;
  let peakOccupiedBeds = initiallyOccupiedBeds;
  let peakBedShortage = 0;

  const daily: DailyCapacity[] = [];

  for (let day = 0; day < horizon; day++) {
    activePatients += dailyAdmissions[day];
    activePatients -= dailyDischarges[day];

    const occupiedBeds = initiallyOccupiedBeds + activePatients;

    const remainingBeds = Math.max(0, totalBeds - occupiedBeds);
    const bedShortage = Math.max(0, occupiedBeds - totalBeds);

    peakOccupiedBeds = Math.max(peakOccupiedBeds, occupiedBeds);
    peakBedShortage = Math.max(peakBedShortage, bedShortage);

    daily.push({
      day: day + 1,
      admissions: dailyAdmissions[day],
      discharges: dailyDischarges[day],
      occupiedBeds,
      remainingBeds,
      bedShortage,
    });
  }

  return {
    daily,
    peakOccupiedBeds,
    peakBedShortage,
    peakOccupancyPercent: (peakOccupiedBeds / totalBeds) * 100,
  };
}

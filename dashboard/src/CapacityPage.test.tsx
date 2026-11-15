import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CapacityPage } from "./App";

vi.mock("./components", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("./components")>();

  return {
    ...original,
    TrendChart: () => <div data-testid="mock-trend-chart" />,
  };
});

const actEnvironment = globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT?: boolean;
};

actEnvironment.IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | undefined;
let container: HTMLDivElement | undefined;

afterEach(async () => {
  if (root) {
    await act(async () => root?.unmount());
    root = undefined;
  }

  container?.remove();
  container = undefined;
  vi.unstubAllGlobals();
});

async function changeInput(label: string, value: string) {
  const labels = Array.from(
    container!.querySelectorAll("label"),
  );

  const field = labels.find((item) =>
    item.textContent?.includes(label),
  );

  const input = field?.querySelector("input");

  if (!input) {
    throw new Error(`Input not found: ${label}`);
  }

  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;

    setter?.call(input, value);

    input.dispatchEvent(
      new Event("input", { bubbles: true }),
    );
  });
}

describe("hospital capacity dashboard interactions", () => {
  it("calculates manual capacity stress and preparedness status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({ status: "available" }),
      })),
    );

    container = document.createElement("div");
    document.body.appendChild(container);

    root = createRoot(container);

    await act(async () => {
      root?.render(<CapacityPage />);
    });

    expect(container.textContent).toContain(
      "Hospital capacity simulator",
    );

    await changeInput("Hypothetical bed capacity", "100");
    await changeInput("Hypothetical occupied beds", "40");
    await changeInput("Additional hypothetical patients", "70");

    expect(container.textContent).toContain(
      "110.0%",
    );

    expect(container.textContent).toContain(
      "Hypothetical demand exceeds capacity",
    );

    expect(container.textContent).toContain(
      "Explore scenarios with additional hypothetical bed capacity.",
    );
  });
});

describe("disease-based hospital capacity interactions", () => {
  it("estimates admissions and updates capacity stress", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<CapacityPage />);
    });

    await changeInput("Hypothetical disease cases", "500");
    await changeInput("Assumed hospitalization rate", "20");
    await changeInput("Hypothetical bed capacity", "100");
    await changeInput("Hypothetical occupied beds", "40");

    const mode = container.querySelector(
      'select[aria-label="Simulation mode"]',
    ) as HTMLSelectElement;

    expect(mode).not.toBeNull();

    await act(async () => {
      mode.value = "disease";
      mode.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(container.textContent).toContain("140.0%");
    expect(container.textContent).toContain(
      "Hypothetical demand exceeds capacity",
    );
    expect(container.textContent).toContain(
      "Additional patients from disease scenario:",
    );
  });
});

describe("length-of-stay dashboard interactions", () => {
  it("shows peak bed demand, daily chart, and preparedness status", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<CapacityPage />);
    });

    await changeInput("Hypothetical bed capacity", "10");
    await changeInput("Hypothetical occupied beds", "5");
    await changeInput("Additional hypothetical patients", "20");
    await changeInput("Admission period (days)", "2");
    await changeInput("Length of stay (days)", "3");

    expect(container.textContent).toContain("250.0%");
    expect(container.textContent).toContain(
      "Peak hypothetical bed shortage",
    );
    expect(container.textContent).toContain(
      "Peak occupancy across the length-of-stay simulation",
    );
    expect(container.textContent).toContain(
      "Hypothetical demand exceeds capacity",
    );
    expect(
      container.querySelector('[data-testid="mock-trend-chart"]'),
    ).not.toBeNull();
  });
});

describe("hospital capacity input validation", () => {
  it("rejects occupied beds greater than hypothetical capacity", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<CapacityPage />);
    });

    await changeInput("Hypothetical bed capacity", "100");
    await changeInput("Hypothetical occupied beds", "150");
    await changeInput("Additional hypothetical patients", "20");

    expect(container.textContent).toContain(
      "Scenario occupied beds cannot exceed the hypothetical capacity.",
    );

    expect(container.textContent).toContain(
      "Enter valid hypothetical inputs for the selected simulation mode.",
    );

    expect(container.textContent).not.toContain(
      "Hypothetical demand exceeds capacity",
    );
  });

  it("does not generate a daily chart for invalid length-of-stay inputs", async () => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root?.render(<CapacityPage />);
    });

    await changeInput("Hypothetical bed capacity", "100");
    await changeInput("Hypothetical occupied beds", "40");
    await changeInput("Additional hypothetical patients", "20");
    await changeInput("Admission period (days)", "0");
    await changeInput("Length of stay (days)", "5");

    expect(container.textContent).toContain(
      "Complete the selected capacity scenario and enter valid",
    );

    expect(
      container.querySelector('[data-testid="mock-trend-chart"]'),
    ).toBeNull();
  });
});

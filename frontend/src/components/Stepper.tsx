import clsx from "clsx";
import { Check } from "lucide-react";

const steps = [
  "Evidence",
  "Map",
  "Scenario",
  "Reconstruct",
  "Trace",
  "Correct",
  "Verdict",
];

export function Stepper({ current }: { current: number }) {
  return (
    <nav className="stepper" aria-label="Audit progress">
      <ol>
        {steps.map((step, index) => {
          const number = index + 1;
          const complete = number < current;
          return (
            <li
              key={step}
              className={clsx(
                "step",
                complete && "complete",
                number === current && "active",
              )}
              aria-current={number === current ? "step" : undefined}
            >
              <span className="step-number">
                {complete ? <Check aria-hidden="true" /> : number}
              </span>
              <span>{step}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// Harness selection and capability/preflight diagnostics — rendered
// entirely from the API's capability descriptors. There is no branch on
// any harness name; unsupported capabilities carry their explicit
// reasons and unknown preflight states are visibly unknown.
import type { HarnessDescriptor } from '../api/client';

interface HarnessPickerProps {
  harnesses: HarnessDescriptor[];
  selected: string | null;
  onSelect: (name: string) => void;
}

export default function HarnessPicker({ harnesses, selected, onSelect }: HarnessPickerProps) {
  return (
    <section aria-label="harness selection">
      <h3>Harness</h3>
      <div role="radiogroup" aria-label="available harnesses">
        {harnesses.map((harness) => (
          <label key={harness.name} data-testid={`harness-option-${harness.name}`}>
            <input
              type="radio"
              name="harness"
              value={harness.name}
              checked={selected === harness.name}
              onChange={() => onSelect(harness.name)}
            />
            <span>
              {harness.name} <small>({harness.version})</small>
            </span>
          </label>
        ))}
      </div>
      {selected && (() => {
        const descriptor = harnesses.find((h) => h.name === selected);
        if (!descriptor) return null;
        return (
          <div data-testid="harness-diagnostics">
            <h4>Capabilities</h4>
            <ul>
              {descriptor.capabilities.length === 0 && (
                <li data-testid="no-optional-capabilities">
                  no optional capabilities — required operations only
                </li>
              )}
              {descriptor.capabilities.map((capability) => (
                <li key={capability} data-testid={`capability-${capability}`}>
                  {capability}: supported
                </li>
              ))}
            </ul>
            <h4>Unsupported controls</h4>
            <ul>
              {descriptor.unsupported_capabilities.map((entry) => (
                <li key={entry.capability} data-testid={`unsupported-${entry.capability}`}>
                  {entry.capability}: {entry.reason}
                </li>
              ))}
            </ul>
            <h4>Preflight</h4>
            <ul>
              {descriptor.preflight.checks.map((check) => (
                <li
                  key={check.name}
                  data-testid={`preflight-${check.name}`}
                  data-status={check.status}
                >
                  {check.name}: {check.status}
                  {check.detail ? ` — ${check.detail}` : ''}
                </li>
              ))}
            </ul>
          </div>
        );
      })()}
    </section>
  );
}
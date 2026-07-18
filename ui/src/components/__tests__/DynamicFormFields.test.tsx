// Contract tests for DynamicFormFields (ARC-011 P3-022, P3-023, P3-028).
//
// These pin the form's riskiest logic: the visible_when conditional language,
// the generic options_url fetch, the plugin-registry extension point, and the
// integer/number zero-value rendering (a regression guard for the T8 coercion
// fix).
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DynamicFormFields from '../DynamicFormFields';
import * as apiModule from '../../api/client';
import { reset as resetPluginRegistry, register } from '../../skill-plugins/registry';
import type { FormField } from '../../api/client';

function makeField(overrides: Partial<FormField> = {}): FormField {
  return { name: 'f', type: 'string', ...overrides };
}

describe('DynamicFormFields', () => {
  describe('field types', () => {
    it('renders a checkbox for boolean fields', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'enable_hpo', type: 'boolean' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      expect(screen.getByRole('checkbox')).toBeInTheDocument();
    });

    it('renders a textarea for text fields', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'notes', type: 'text' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      // textarea has no implicit role beyond 'textbox'; query by tag.
      expect(document.querySelector('textarea')).toBeInTheDocument();
    });

    it('renders a select with declared options for enum fields', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'mode', type: 'enum', enum: ['a', 'b'] })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      const select = screen.getByRole('combobox') as HTMLSelectElement;
      expect([...select.options].map((o) => o.value)).toEqual(['', 'a', 'b']);
    });

    it('renders a number input for integer and number fields', () => {
      const { rerender } = render(
        <DynamicFormFields
          fields={[makeField({ name: 'trials', type: 'integer' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      expect(screen.getByRole('spinbutton')).toHaveAttribute('type', 'number');
      rerender(
        <DynamicFormFields
          fields={[makeField({ name: 'lr', type: 'number' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      expect(screen.getByRole('spinbutton')).toHaveAttribute('type', 'number');
    });
  });

  describe('integer/number zero-value rendering (T8 regression guard)', () => {
    // Before T8, `value={value as number ?? ''}` coerced 0 to '' because the
    // nullish-ish `?? ''` ran after the `as number` cast (0 is falsy under the
    // loose guard). The fix uses a real nullish check.
    it('renders 0 for an integer field when the value is 0', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'trials', type: 'integer' })]}
          values={{ trials: 0 }}
          onChange={() => {}}
        />,
      );
      const input = screen.getByRole('spinbutton') as HTMLInputElement;
      expect(input.value).toBe('0');
    });

    it('renders 0 for a number field when the value is 0', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'lr', type: 'number' })]}
          values={{ lr: 0 }}
          onChange={() => {}}
        />,
      );
      const input = screen.getByRole('spinbutton') as HTMLInputElement;
      expect(input.value).toBe('0');
    });

    it('renders empty for a number field when the value is absent', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'lr', type: 'number' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      const input = screen.getByRole('spinbutton') as HTMLInputElement;
      expect(input.value).toBe('');
    });
  });

  describe('visible_when (P3-023)', () => {
    it('hides a field whose visible_when condition is unmet', () => {
      render(
        <DynamicFormFields
          fields={[
            makeField({ name: 'hpo_trials', type: 'integer', visible_when: { field: 'enable_hpo', equals: 'true' } }),
          ]}
          values={{ enable_hpo: 'false' }}
          onChange={() => {}}
        />,
      );
      expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    });

    it('shows a field whose visible_when condition is met', () => {
      render(
        <DynamicFormFields
          fields={[
            makeField({ name: 'hpo_trials', type: 'integer', visible_when: { field: 'enable_hpo', equals: 'true' } }),
          ]}
          values={{ enable_hpo: 'true' }}
          onChange={() => {}}
        />,
      );
      expect(screen.getByRole('spinbutton')).toBeInTheDocument();
    });

    it('resolves visible_when against skillId when the condition field is skill_id', () => {
      render(
        <DynamicFormFields
          fields={[
            makeField({ name: 'rl_only', type: 'string', visible_when: { field: 'skill_id', equals: 'ml-rl' } }),
          ]}
          values={{}}
          onChange={() => {}}
          skillId="ml-rl"
        />,
      );
      // visible_when satisfied via skillId → the field renders.
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });

    it('does not round-trip to the server when toggling visibility', () => {
      const getSpy = vi.spyOn(apiModule.api, 'getSubjects');
      const { rerender } = render(
        <DynamicFormFields
          fields={[
            makeField({ name: 'rl_only', type: 'string', visible_when: { field: 'flag', equals: 'on' } }),
          ]}
          values={{ flag: 'off' }}
          onChange={() => {}}
        />,
      );
      rerender(
        <DynamicFormFields
          fields={[
            makeField({ name: 'rl_only', type: 'string', visible_when: { field: 'flag', equals: 'on' } }),
          ]}
          values={{ flag: 'on' }}
          onChange={() => {}}
        />,
      );
      expect(getSpy).not.toHaveBeenCalled();
      getSpy.mockRestore();
    });
  });

  describe('unknown field type fallback (P3-028 generic fallback)', () => {
    it('renders a text input and a warning for an unknown field type', () => {
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'weird', type: 'hpo_matrix' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      expect(screen.getByText(/Unknown field type "hpo_matrix"/)).toBeInTheDocument();
    });
  });

  describe('plugin registry (P3-028 extension point)', () => {
    beforeEach(() => resetPluginRegistry());
    afterEach(() => resetPluginRegistry());

    it('renders a registered plugin for a custom field type and suppresses the warning', () => {
      register({
        id: 'hpo-matrix-plugin',
        canRender: (f) => f.type === 'hpo_matrix',
        render: ({ value, onChange }) => (
          <input
            data-testid="hpo-matrix"
            value={String(value ?? '')}
            onChange={(e) => onChange(e.target.value)}
          />
        ),
      });
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'matrix', type: 'hpo_matrix' })]}
          values={{ matrix: '3x3' }}
          onChange={() => {}}
        />,
      );
      expect(screen.getByTestId('hpo-matrix')).toBeInTheDocument();
      // Plugin handles the field → no generic-fallback warning.
      expect(screen.queryByText(/Unknown field type/)).not.toBeInTheDocument();
    });

    it('falls back to the generic renderer when no plugin matches', () => {
      register({
        id: 'unrelated-plugin',
        canRender: (f) => f.type === 'something_else',
        render: () => <input data-testid="unrelated" />,
      });
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'matrix', type: 'hpo_matrix' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      expect(screen.queryByTestId('unrelated')).not.toBeInTheDocument();
      expect(screen.getByText(/Unknown field type "hpo_matrix"/)).toBeInTheDocument();
    });
  });

  describe('options_url (P3-023 generic fetch)', () => {
    it('dispatches to getSubjects for a /subjects options_url', async () => {
      const getSpy = vi.spyOn(apiModule.api, 'getSubjects').mockResolvedValue([
        { id: 'DOGE_USDT', label: 'Doge' },
        { id: 'BTC_USDT', label: 'Bitcoin' },
      ]);
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'subject', type: 'enum_dynamic', options_url: '/subjects?skill_id=ml-direction' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      // The fetch is keyed on skill_id query param generically (no string-split).
      expect(getSpy).toHaveBeenCalledWith('ml-direction');
      const select = await screen.findByRole('combobox') as HTMLSelectElement;
      expect([...select.options].map((o) => o.value)).toEqual(['', 'DOGE_USDT', 'BTC_USDT']);
      getSpy.mockRestore();
    });

    it('dispatches to getSubjectVariants for a /subjects/{id}/variants options_url', async () => {
      const variantsSpy = vi.spyOn(apiModule.api, 'getSubjectVariants').mockResolvedValue({
        skill_id: 'ml-direction', subject_id: 'DOGE_USDT', variants: ['15m', '1h'],
      });
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'variant', type: 'enum_dynamic', options_url: '/subjects/DOGE_USDT/variants?skill_id=ml-direction' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      expect(variantsSpy).toHaveBeenCalledWith('DOGE_USDT', 'ml-direction');
      const select = await screen.findByRole('combobox') as HTMLSelectElement;
      expect([...select.options].map((o) => o.value)).toEqual(['', '15m', '1h']);
      variantsSpy.mockRestore();
    });

    it('renders an empty select when the options_url shape is unrecognized', async () => {
      const getSpy = vi.spyOn(apiModule.api, 'getSubjects').mockResolvedValue([]);
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'weird', type: 'enum_dynamic', options_url: '/unknown-endpoint?x=1' })]}
          values={{}}
          onChange={() => {}}
        />,
      );
      // Unknown path → no api method called → empty options; form stays usable.
      expect(getSpy).not.toHaveBeenCalled();
      const select = await screen.findByRole('combobox') as HTMLSelectElement;
      expect([...select.options].map((o) => o.value)).toEqual(['']);
      getSpy.mockRestore();
    });
  });

  describe('onChange wiring', () => {
    it('propagates text input changes by field name', async () => {
      const user = userEvent.setup();
      const onChange = vi.fn();
      render(
        <DynamicFormFields
          fields={[makeField({ name: 'tag', type: 'string' })]}
          values={{}}
          onChange={onChange}
        />,
      );
      await user.type(screen.getByRole('textbox'), 'x');
      expect(onChange).toHaveBeenCalledWith('tag', 'x');
    });
  });
});

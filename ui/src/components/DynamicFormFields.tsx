// Dynamic form renderer — renders any skill's form from /form-fields data
// with zero hardcoded fields (ARC-011 P3-022, P3-023, P3-028).
//
// Field types supported: string, text, integer, number, boolean, enum,
// enum_dynamic. `visible_when` hides/shows fields client-side. `options_url`
// fetches dynamic options lazily. Unknown field types fall back to text +
// warning (P3-022 AC #6, P3-028 generic fallback).
import { useEffect, useState } from 'react';
import type { FormField } from '../api/client';
import { api } from '../api/client';
import { resolve as resolvePlugin } from '../skill-plugins/registry';
import { Field } from './hifi/primitives';

interface Props {
  fields: FormField[];
  values: Record<string, unknown>;
  onChange: (name: string, value: unknown) => void;
  // The current skill_id — used for `visible_when` skill_id match conditions.
  skillId?: string;
}

// Track which field types are known vs. fallback (P3-028).
const KNOWN_TYPES = new Set(['string', 'text', 'integer', 'number', 'boolean', 'enum', 'enum_dynamic']);

/**
 * P3-023: fetch dynamic options for an `enum_dynamic` field from its
 * `options_url`. URL-shape-agnostic — parses the URL generically and dispatches
 * to the matching `api.*` method by pathname, threading through any query
 * params. Supports the subject (`/subjects?skill_id=…`) and variant
 * (`/subjects/{id}/variants?skill_id=…`) endpoints today; unknown paths reject
 * so a malformed options_url surfaces as an empty list (form stays usable).
 */
async function fetchDynamicOptions(optionsUrl: string): Promise<string[]> {
  // options_url is a relative API path; give URL a base so it parses.
  const url = new URL(optionsUrl, 'http://api.local');
  const params = url.searchParams;
  const skillId = params.get('skill_id') || '';
  // /subjects → subject ids; /subjects/{id}/variants → variant strings.
  if (url.pathname === '/subjects') {
    const subjects = await api.getSubjects(skillId);
    return subjects.map((s) => s.id);
  }
  const variantMatch = url.pathname.match(/^\/subjects\/([^/]+)\/variants$/);
  if (variantMatch) {
    const subjectId = decodeURIComponent(variantMatch[1]);
    const result = await api.getSubjectVariants(subjectId, skillId);
    return result.variants;
  }
  return [];
}

export default function DynamicFormFields({ fields, values, onChange, skillId }: Props) {
  return (
    <div className="col gap-3">
      {fields.map((field) => (
        <FieldRow
          key={field.name}
          field={field}
          values={values}
          onChange={onChange}
          skillId={skillId}
          allFields={fields}
        />
      ))}
    </div>
  );
}

function FieldRow({
  field,
  values,
  onChange,
  skillId,
  allFields,
}: {
  field: FormField;
  values: Record<string, unknown>;
  onChange: (name: string, value: unknown) => void;
  skillId?: string;
  allFields: FormField[];
}) {
  // P3-023: visible_when conditional — hide/show without a server round-trip.
  if (field.visible_when) {
    const cond = field.visible_when;
    // Support {field: "skill_id", equals: "ml-rl"} style conditions.
    const fieldValue = cond.field === 'skill_id' ? skillId : values[cond.field];
    if (fieldValue !== cond.equals) return null;
  }

  const isKnown = KNOWN_TYPES.has(field.type);
  const effectiveType = isKnown ? field.type : 'string';
  // P3-028: a skill plugin may render this field. The registry is the
  // extension point — a skill ships a renderer instead of forcing a new branch
  // here. Unknown built-in types fall through to the plugin registry too.
  const plugin = resolvePlugin(field);
  const usesPlugin = plugin !== null;

  return (
    <div>
      <Field label={field.description || field.name}>
        {usesPlugin ? (
          plugin!.render({
            field,
            value: values[field.name] ?? field.default ?? '',
            onChange: (v) => onChange(field.name, v),
          })
        ) : (
          <FieldInput
            field={field}
            effectiveType={effectiveType}
            value={values[field.name] ?? field.default ?? ''}
            onChange={(v) => onChange(field.name, v)}
          />
        )}
      </Field>
      {!isKnown && !usesPlugin && (
        <div className="text-xs text-yellow-500 mt-1">
          ⚠ Unknown field type "{field.type}" — rendered as text input
        </div>
      )}
    </div>
  );
}

function FieldInput({
  field,
  effectiveType,
  value,
  onChange,
}: {
  field: FormField;
  effectiveType: string;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  // P3-023: enum_dynamic fetches options lazily from options_url.
  const [dynamicOptions, setDynamicOptions] = useState<string[] | null>(null);

  useEffect(() => {
    if (effectiveType === 'enum_dynamic' && field.options_url && dynamicOptions === null) {
      fetchDynamicOptions(field.options_url)
        .then(setDynamicOptions)
        .catch(() => setDynamicOptions([]));
    }
  }, [effectiveType, field.options_url, dynamicOptions]);

  switch (effectiveType) {
    case 'boolean':
      return (
        <label className="row gap-2 items-center" style={{ fontSize: 14 }}>
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(e) => onChange(e.target.checked)}
          />
          <span>{field.name}</span>
        </label>
      );

    case 'integer':
      return (
        <input
          className="input mono"
          type="number"
          value={value == null ? '' : (value as number)}
          onChange={(e) => onChange(e.target.value === '' ? undefined : parseInt(e.target.value, 10))}
          min={field.min}
          max={field.max}
          step={1}
        />
      );

    case 'number':
      return (
        <input
          className="input mono"
          type="number"
          value={value == null ? '' : (value as number)}
          onChange={(e) => onChange(e.target.value === '' ? undefined : parseFloat(e.target.value))}
          min={field.min}
          max={field.max}
        />
      );

    case 'text':
      return (
        <textarea
          className="input mono"
          value={value as string ?? ''}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
        />
      );

    case 'enum':
      return (
        <select
          className="select mono"
          value={value as string ?? ''}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">— select —</option>
          {(field.enum || []).map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );

    case 'enum_dynamic':
      return (
        <select
          className="select mono"
          value={value as string ?? ''}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">— select —</option>
          {(dynamicOptions || []).map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );

    default: // 'string' and unknown-type fallback
      return (
        <input
          className="input mono"
          type="text"
          value={value as string ?? ''}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

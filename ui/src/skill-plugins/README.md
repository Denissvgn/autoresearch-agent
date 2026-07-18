# Skill plugin renderer registry (ARC-011 P3-028)

The extension point that keeps the "drop a directory, no UI code changes"
guarantee (ARC-011 §7.14) honest on the frontend.

## Why

`DynamicFormFields` renders any skill's form from `GET /skills/{id}/form-fields`
data. It knows the seven built-in field types (`string`, `text`, `integer`,
`number`, `boolean`, `enum`, `enum_dynamic`). A skill that needs a richer
control — a matrix editor, a dual-list selector, a domain-specific picker —
should not force a new branch into the generic form component. Instead the
skill ships a renderer that the registry resolves at render time.

## How to ship a renderer

1. Create a renderer implementing `SkillPluginRenderer` (see `types.ts`):

   ```ts
   import type { SkillPluginRenderer } from '.';
   import { register } from '.';

   export const rlHpoMatrix: SkillPluginRenderer = {
     id: 'rl-hpo-matrix',
     canRender: (field) => field.type === 'hpo_matrix',
     render: ({ field, value, onChange }) => (
       /* your control */
     ),
   };

   register(rlHpoMatrix);
   ```

2. Import the renderer module from the app entrypoint (or from
   `skill-plugins/index.ts`) so the `register()` side effect runs.

3. In the skill's `SKILL.yaml` `ui.form_fields`, declare the field with the
   custom `type` (`hpo_matrix` above). `DynamicFormFields` consults the registry
   before its built-in switch; the renderer wins.

## Resolution order

The first registered renderer whose `canRender(field)` returns `true` wins. If
none match, `resolve()` returns `null` and `DynamicFormFields` falls back to a
text input + warning (the P3-028 generic fallback) — so an unknown field type
never breaks the form.

## Testing

`registry.ts` exposes a `reset()` for tests. Register the renderer under test,
assert it renders for the matching field and that the generic fallback is used
otherwise, then `reset()`.

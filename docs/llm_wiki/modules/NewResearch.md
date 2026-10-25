# NewResearch Module

**Path:** `ui/src/pages/NewResearch.tsx`

## Description

_Auto-generated from `ui/src/pages/NewResearch.tsx`._

## Imports

| Source | Symbols |
|--------|---------|
| `../components/DynamicFormFields` | `DynamicFormFields` |
| `../components/HarnessPicker` | `HarnessPicker` |
| `../components/SkillPicker` | `SkillPicker` |
| `../components/hifi/primitives` | `Field`, `Icon` |
| `../hooks/useResearch` | `useModels`, `useStartResearch`, `useSkills`, `useSkillFormFields`, `useCostEstimate`, `useHarnesses` |
| `react` | `useEffect`, `useMemo`, `useState` |
| `react-router-dom` | `Link`, `useNavigate` |

## Module Signals

| Signal | Values |
|--------|--------|
| Exports | `default` |
| Constants | `FOCUS_EXAMPLES` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["ui/src/App.tsx"]
    n1["ui/src/components/DynamicFormFields.tsx"]
    n2["ui/src/components/HarnessPicker.tsx"]
    n3["ui/src/components/hifi/primitives.tsx"]
    n4["ui/src/components/SkillPicker.tsx"]
    n5["ui/src/hooks/useResearch.ts"]
    n6["ui/src/pages/__tests__/NewResearch.test.tsx"]
    n7["ui/src/pages/NewResearch.tsx"]
    n0 --> n3
    n0 --> n5
    n0 --> n7
    n1 --> n3
    n6 --> n7
    n7 --> n1
    n7 --> n2
    n7 --> n3
    n7 --> n4
    n7 --> n5
    click n0 "../modules/App.md"
    click n1 "../modules/DynamicFormFields.md"
    click n2 "../modules/HarnessPicker.md"
    click n3 "../modules/primitives.md"
    click n4 "../modules/SkillPicker.md"
    click n5 "../modules/useResearch.md"
    click n6 "../modules/NewResearch.test.md"
    click n7 "../modules/NewResearch.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Inbound | [App](../modules/App.md) |
| Inbound | [NewResearch.test](../modules/NewResearch.test.md) |
| Outbound | [DynamicFormFields](../modules/DynamicFormFields.md) |
| Outbound | [HarnessPicker](../modules/HarnessPicker.md) |
| Outbound | [primitives](../modules/primitives.md) |
| Outbound | [SkillPicker](../modules/SkillPicker.md) |
| Outbound | [useResearch](../modules/useResearch.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| typescript | 2 | 0 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `NewResearch` | `()` | — | — |

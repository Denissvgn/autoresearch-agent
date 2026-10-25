# FormField

**Location:** `ui/src/api/client.ts:501`
**Kind:** Class
**Bases:** —
**Module:** [client](../modules/client.md)

## Description

_Auto-generated from `FormField` in `ui/src/api/client.ts`._

## Attributes

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `name` | `string` | Yes | — | — |
| `type` | `string` | Yes | — | — |
| `description` | `string` | No | — | — |
| `default` | `unknown` | No | — | — |
| `min` | `number` | No | — | — |
| `max` | `number` | No | — | — |
| `enum` | `string[]` | No | — | — |
| `options_url` | `string` | No | — | — |
| `visible_when` | `{ field: string; equals: string }` | No | — | — |
| `required` | `boolean` | No | — | — |

## Methods

*No public methods. Inherits from base classes.*

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["FormField (ui/src/api/client.ts)"]
    n1["ui/src/components/__tests__/DynamicFormFields.test.tsx"]
    n2["ui/src/components/DynamicFormFields.tsx"]
    n3["resolve (ui/src/skill-plugins/registry.ts)"]
    n4["ui/src/skill-plugins/types.ts"]
    n1 --> n0
    n2 --> n0
    n3 --> n0
    n4 --> n0
    click n0 "../modules/client.md"
    click n1 "../modules/DynamicFormFields.test.md"
    click n2 "../modules/DynamicFormFields.md"
    click n3 "../modules/registry.md"
    click n4 "../modules/types.md"
```

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [client](../modules/client.md) | 0 | `default`, `description`, `enum`, `max`, `min`, `name`, `options_url`, `required`, `type`, `visible_when` |

### References

| Reference | Kind | Source | Call sites |
|---|---|---|---:|
| `DynamicFormFields.test` | import | [DynamicFormFields.test](../modules/DynamicFormFields.test.md) | — |
| `DynamicFormFields` | import | [DynamicFormFields](../modules/DynamicFormFields.md) | — |
| `resolve` | type_reference | [registry](../modules/registry.md) | — |
| `types` | import | [types](../modules/types.md) | — |

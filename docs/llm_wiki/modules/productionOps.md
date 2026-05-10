# productionOps Module

**Path:** `ui/src/utils/productionOps.ts`

## Description

_Auto-generated from `ui/src/utils/productionOps.ts`._

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [BlockerDetailShape](../entities/BlockerDetailShape.md) | 4 | — | — |
| [ProductionWarningShape](../entities/ProductionWarningShape.md) | 9 | — | — |
| [PromotionScopeStatusShape](../entities/PromotionScopeStatusShape.md) | 15 | — | — |
| [ProductionOperationsShape](../entities/ProductionOperationsShape.md) | 25 | — | — |
| [OpsTone](../entities/OpsTone.md) | 1 | — | — |
| [PromotionScopeName](../entities/PromotionScopeName.md) | 2 | — | — |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `humanizeBlocker` | `(code: string) -> string` | — | — |
| `blockerLabels` | `(blockers: string[], details: BlockerDetailShape[]) -> string[]` | — | — |
| `scopeLabel` | `(scope: PromotionScopeName) -> string` | — | — |
| `toneForStatus` | `(status: string | null) -> OpsTone` | — | — |
| `toneClasses` | `(tone: OpsTone) -> string` | — | — |
| `scopeSummary` | `(scope: PromotionScopeStatusShape) -> {
  label: string;
  tone: OpsTone;
  message: string;
  canConfirm: boolean;
}` | — | — |
| `warningTone` | `(warning: ProductionWarningShape) -> OpsTone` | — | — |
| `formatMetric` | `(value: unknown) -> string` | — | — |
| `productionReady` | `(ops: ProductionOperationsShape | null) -> boolean` | — | — |

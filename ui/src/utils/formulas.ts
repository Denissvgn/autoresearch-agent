/**
 * Solves logical hardcodings for RL composite formulations.
 * These align with orchestrator.py: 1.0*sharpe + 0.5*return - 2.0*drawdown - 0.1*cv
 */
export const RL_COMPOSITE_COEFFICIENTS = {
  sharpe: { weight: 1.0, label: 'Sharpe ratio multiplier' },
  return: { weight: 0.5, label: 'OOS return multiplier' },
  drawdown: { weight: 2.0, label: 'OOS drawdown multiplier' },
  cv: { weight: 0.1, label: 'Sharpe coefficient of variance penalty' },
};

export function calculateCompositeRLScore(
  sharpe: number,
  oosReturn: number,
  drawdown: number,
  cv: number
): {
  termS: number;
  termR: number;
  termD: number;
  termCV: number;
  total: number;
} {
  const termS = RL_COMPOSITE_COEFFICIENTS.sharpe.weight * sharpe;
  const termR = RL_COMPOSITE_COEFFICIENTS.return.weight * oosReturn;
  const termD = RL_COMPOSITE_COEFFICIENTS.drawdown.weight * drawdown;
  const termCV = RL_COMPOSITE_COEFFICIENTS.cv.weight * cv;
  const total = termS + termR - termD - termCV;
  return { termS, termR, termD, termCV, total };
}

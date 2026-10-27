"""Kundu–Raqab (2009) MMLE, single-sample minimum-delete-one construction.

Matches the archived Research09 KROriginal fixed-point arithmetic. The paper
uses alpha for shape and theta=eta**beta for its scale parametrization:
SPL 79(17), 1839–1846; p.1840 (4), p.1841 (6), (9)–(11).
The previous Cohen–Whitten implementation is preserved in methods.mmle_ch.
"""
import numpy as np
from scipy.special import logsumexp

from base import WeibullBase

INITIAL_SHAPE = 1.0
SHAPE_ABSOLUTE_STEP_TOLERANCE = 1e-8
MAX_ITERATIONS = 10000


class MMLE(WeibullBase):
    """Fix gamma at the original minimum, delete it, then fit shifted data.

    No Firth adjustment, shape/location caps, restart or fallback solver.
    The retained observations, rather than the deleted minimum, define support.
    """

    def run(self, trace=False, *, initial_shape=INITIAL_SHAPE,
            shape_absolute_step_tolerance=SHAPE_ABSOLUTE_STEP_TOLERANCE,
            max_iterations=MAX_ITERATIONS):
        """Return [beta, eta, gamma, 0.0, converged], as in KROriginal.

        R² is the archived zero placeholder; the original minimum has zero
        shifted distance, so the full-sample log-linear R² is not evaluated.
        """
        if not np.isfinite(initial_shape) or initial_shape <= 0:
            raise ValueError('initial_shape must be finite and positive')
        if (not np.isfinite(shape_absolute_step_tolerance)
                or shape_absolute_step_tolerance <= 0):
            raise ValueError('shape_absolute_step_tolerance must be finite and positive')
        if (isinstance(max_iterations, bool)
                or not isinstance(max_iterations, (int, np.integer))
                or max_iterations < 1):
            raise ValueError('max_iterations must be a positive integer')
        if self.n < 2:
            self.last_solution_info = {'status': 'insufficient_sample', 'n': self.n}
            return [None, None, None, 0., False]

        gamma = float(self.data[0])
        y = self.data[1:] - gamma
        beta = float(initial_shape)
        converged = False
        history = []
        difference = float('inf')
        # Invalid steps fail under the original rule; they do not trigger rescue.
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            logs = np.log(y)
            q = len(y)
            for iteration in range(1, max_iterations + 1):
                weights = np.exp(beta * (logs - logs.max()))
                weights /= weights.sum()
                denominator = float(q * (weights @ logs))
                next_beta = float((q + beta * logs.sum()) / denominator)
                if not np.isfinite(next_beta) or next_beta <= 0:
                    break
                difference = abs(next_beta - beta)
                if iteration <= 3:
                    history.append(dict(iteration=iteration, shape_before=beta,
                                        shape_after=next_beta))
                if trace:
                    self.log_step(dict(phase='shape_iteration', iteration=iteration,
                                       shape_before=beta, shape_after=next_beta,
                                       shape_step=float(difference)))
                beta = next_beta
                if difference <= shape_absolute_step_tolerance:
                    converged = True
                    break
            self.last_solution_info = dict(
                status='ok' if converged else 'fixed_point_not_converged',
                iterations=iteration, initial_shape=float(initial_shape),
                final_shape_step=float(difference), deleted_observations=1,
                gamma_is_original_sample_minimum=True,
                effective_sample_min=float(self.data[1]), first_iterations=history,
                no_firth=True, no_domain_caps=True, no_fallback=True,
                shape_absolute_step_tolerance=float(shape_absolute_step_tolerance),
                max_iterations=int(max_iterations))
            if not converged:
                return [None, None, None, 0., False]
            eta = float(np.exp((logsumexp(beta * logs) - np.log(q)) / beta))
        if trace:
            self.log_step(dict(phase='final', beta=beta, eta=eta, gamma=gamma,
                               **self.last_solution_info))
        return [beta, eta, gamma, 0., True]

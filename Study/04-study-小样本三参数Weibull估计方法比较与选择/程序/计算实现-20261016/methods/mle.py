"""Finite local MLE with explicit engineering constraints and profile search.

The statistical likelihood and beta>=1, gamma>=0 convention are unchanged.
Open-support limits are diagnostics, not artificial finite estimates.
"""
from base import WeibullBase
from .profile_solvers import solve_mle_profile


class MLE(WeibullBase):
    def run(self, trace=False):
        # @step: 1 | 条件似然求解 | 固定位置后求形状并恢复尺度
        # @formula: eta=(mean((x-gamma)**beta))**(1/beta)
        # @step: 2 | 位置搜索 | 扫描并精化有限局部极大与零位置边界
        # @step: 3 | 候选比较 | 按原似然选择有限候选，另记支持边界极限
        try:
            selected, info = solve_mle_profile(self.data)
        except (ValueError, FloatingPointError, RuntimeError) as error:
            self.last_solution_info = dict(status='profile_solver_failed', error=str(error))
            return [None, None, None, 0., 'profile_solver_failed']
        self.last_solution_info = info
        if trace:
            for candidate in info.get('candidates', []):
                self.log_step(dict(phase='candidate', beta=candidate['beta'],
                                   eta=candidate['eta'], gamma=candidate['gamma'],
                                   log_likelihood=candidate['ll'], kind=candidate['kind']))
        if selected is None:
            if trace:
                self.log_step(dict(phase='failed', reason=info['status']))
            return [None, None, None, 0., info['status']]
        beta, eta, gamma = (selected[p] for p in ['beta', 'eta', 'gamma'])
        if trace:
            self.log_step(dict(phase='final', beta=beta, eta=eta, gamma=gamma,
                               log_likelihood=selected['ll'], converged=True))
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma), True]

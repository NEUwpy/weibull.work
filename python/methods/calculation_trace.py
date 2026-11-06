"""Backend-owned plot values from a single estimation run.

No estimator or surrogate formula lives here. The caller supplies quantities
already evaluated by the solver, or explicitly identified supplementary
evaluations of the same objective. Candidate comparison is not an iteration.
"""
import math


def plot_point(x, y, **extra):
    if not (math.isfinite(float(x)) and math.isfinite(float(y))):
        return None
    return dict(x=float(x), y=float(y), **extra)


def plot_series(key, label, points, *, role='solver', kind='line'):
    actual_points = [p for p in points if p is not None]
    if kind == 'line':
        actual_points.sort(key=lambda point: point['x'])
    return dict(id=key, label=label, kind=kind, role=role,
                points=actual_points)


def plot_chart(key, title, x_label, y_label, series, *, description='',
               references=None, selected=None, formula=None):
    return dict(id=key, title=title, description=description,
                x=dict(key='x', label=x_label), y=dict(key='y', label=y_label),
                series=series, references=references or [],
                selected=[p for p in (selected or []) if p is not None],
                **(dict(formula=formula) if formula else {}))


def calculation_step(title, formula, values):
    """Explain parameter recovery from solver-owned scalars, without recomputing it."""
    return dict(title=title, formula=formula,
                values=[dict(label=label, value=float(value)) for label, value in values
                        if value is not None and math.isfinite(float(value))])


def power_scale_calculation(data, beta, gamma, eta, *, normalizer=1.0, first_index=1):
    """Trace the scale identity after selection; never feed it back to a solver.

    Normalized powers also keep the explanation finite when raw powers overflow.
    The returned eta remains the estimator's value, not this diagnostic's result.
    """
    import numpy as np

    observations = np.asarray(data, dtype=float)
    distances = observations - gamma
    reference = float(np.max(distances))
    log_powers = beta * np.log(distances)
    scaled = np.exp(beta * (np.log(distances) - np.log(reference)))
    scaled_sum = float(np.sum(scaled))
    divisor = float(len(observations) * normalizer)
    scaled_mean = scaled_sum / divisor

    def finite_exp(log_value):
        return float(math.exp(log_value)) if log_value <= math.log(np.finfo(float).max) else None

    log_sum = float(beta * np.log(reference) + np.log(scaled_sum))
    total = finite_exp(log_sum)
    mean = finite_exp(log_sum - np.log(divisor))
    return dict(beta=float(beta), gamma=float(gamma), eta=float(eta), count=len(observations),
                normalizer=float(normalizer), divisor=divisor, power_sum=total, power_mean=mean,
                reference_distance=reference, scaled_sum=scaled_sum, scaled_mean=scaled_mean,
                scale_factor=float(scaled_mean ** (1.0 / beta)),
                use_scaled=total is None or mean is None or mean == 0,
                samples=[dict(index=i + first_index, observation=float(t), distance=float(d),
                              power=finite_exp(float(p)), scaled_power=float(s))
                         for i, (t, d, p, s) in enumerate(zip(observations, distances, log_powers, scaled))])


def regression_calculation(points):
    """Expose the sums of the displayed regression, without selecting a fit."""
    import numpy as np

    x = np.array([p['x'] for p in points])
    y = np.array([p['y'] for p in points])
    fitted = np.array([p['fit'] for p in points])
    dx, dy = x-x.mean(), y-y.mean()
    return dict(count=len(x), x_mean=float(x.mean()), y_mean=float(y.mean()),
                sxx=float(dx @ dx), syy=float(dy @ dy), sxy=float(dx @ dy),
                residual_sum=float(np.sum((y-fitted)**2)))


def _profile_reading_frames(method, data, selected, weights=None, solver_shape_values=()):
    """Supplement the unchanged estimate with linked views of its own equations."""
    import numpy as np
    from .conditional_profiles import mle_profile, wmle_profile

    minimum = float(np.min(data))
    location = float(selected['gamma'])
    locations = np.unique(np.r_[np.linspace(0., minimum * .995, 17),
        np.linspace(max(0., location - minimum * .08),
                    min(minimum * .9999, location + minimum * .08), 9), location])
    frames = []
    for gamma in locations:
        evaluations = []
        point = (mle_profile(data, float(gamma), shape_evaluations=evaluations)
                 if method == 'mle' else
                 wmle_profile(data, float(gamma), weights, shape_evaluations=evaluations))
        if point is None:
            continue
        final = bool(gamma == location)
        beta = float(selected['beta'] if final else point['beta'])
        eta = float(selected['eta'] if final else point['eta'])
        score = point['shape_score'] if method == 'mle' else (selected['t1'] if final else point['t1'])
        curve = [p for p in evaluations if p['source'] == 'diagnostic']
        formula = (r'S_\beta=\frac1\beta+\overline{\ln d}-\frac{\sum d_i^\beta\ln d_i}{\sum d_i^\beta}=0'
                   if method == 'mle' else
                   r'T_1=\frac{J_2}{\beta}+\overline{\ln d}-\frac{\sum d_i^\beta\ln d_i}{\sum d_i^\beta}=0')
        if method == 'mle' and point['shape_at_lower_boundary']:
            formula = r'\beta^*(\gamma)=1,\quad S_\beta(1;\gamma)\leq0'
        frame = dict(gamma=float(gamma), beta=beta, eta=eta, final=final,
                     shape_chart=plot_chart('linked-shape-equation',
                         '在这个位置，形状怎样确定', '形状参数 β',
                         '形状得分 Sβ' if method == 'mle' else '加权形状方程 T₁',
                         [plot_series('shape', '同一方程曲线（补充采样）',
                                      [plot_point(p['beta'], p['score']) for p in curve], role='diagnostic')],
                         formula=formula,
                         description='改变查看位置后，对同一现行形状方程求值；辅助曲线不表示求解迭代。',
                         references=[dict(axis='y', value=0., label='方程零线')],
                         selected=[plot_point(beta, score, label='该位置的形状')]))
        if final and solver_shape_values:
            frame['shape_chart']['series'].append(plot_series('solver-points', '本次求解计算点',
                [plot_point(p['beta'], p['score'], evaluation=i+1)
                 for i, p in enumerate(solver_shape_values) if p['source'] == 'solver'], kind='scatter'))
        if method == 'mle':
            frame.update(log_likelihood=float(selected['ll'] if final else point['ll']),
                         location_score=float(point['location_score']))
        else:
            frame.update(**{key: float(point[key]) for key in ('t1', 't2', 'j1', 'j2', 'j3')})
            if final:
                frame.update(t1=float(selected['t1']), t2=float(selected['t2']),
                             j3=float(weights.get_weight_j3(len(data), beta)))
        frames.append(frame)
    return frames


def modified_likelihood_plot(logs, iterations, beta, eta, initial_shape):
    """Single-sample form of Kundu–Raqab's modified profile likelihood."""
    import numpy as np
    from scipy.special import logsumexp

    q = len(logs)

    def point(shape, **extra):
        log_power_mean = float(logsumexp(shape * logs) - np.log(q))
        likelihood = float(q * np.log(shape) - q * log_power_mean
                           + (shape - 1) * np.sum(logs) - q)
        return plot_point(shape, likelihood, eta=float(np.exp(log_power_mean / shape)), **extra)

    stride = max(1, len(iterations) // 24)
    visible = iterations[::stride]
    if iterations and visible[-1] is not iterations[-1]:
        visible.append(iterations[-1])
    frames = [point(float(initial_shape), iteration=0)] + [
        point(p['shape_after'], iteration=p['iteration']) for p in visible]
    lower = max(1e-8, min(beta * .5, initial_shape))
    upper = max(beta * 1.5, initial_shape)
    curve = [point(float(b)) for b in np.unique(np.r_[
        np.linspace(lower, upper, 101), beta, [p['x'] for p in frames]])]
    chart = plot_chart('modified-profile-likelihood', '形状为什么取这个值', '形状参数 β（原文 α）',
        '修改剖面对数似然 ℓₚ',
        [plot_series('profile', '修改似然曲线（补充采样）', curve, role='diagnostic'),
         plot_series('iterations', '实际迭代到达的形状',
                     [point(float(initial_shape), iteration=0)] +
                     [point(p['shape_after'], iteration=p['iteration']) for p in iterations], kind='scatter')],
        formula=r'\ell_p(\beta)=\ell\{\beta,\eta(\beta),\hat\gamma\},\quad\hat\gamma=t_{(1)}',
        description='按原文剖面似然图的思路展示单样本形式；曲线与迭代点使用同一组保留距离、同一单位和同一似然。',
        selected=[point(float(beta), label='最终形状参数')])
    chart['selected'][0]['eta'] = float(eta)
    return chart, frames


def profile_calculation(method, info, selected, *, data=None, weights=None):
    """Present profile samples and candidates without inventing a solver path."""
    profiles = info.get('profile_trace', [])
    candidates = info.get('candidates', [])
    selection = dict(description='', status=info['status'])
    if selected:
        selection.update({p: float(selected[p]) for p in ['beta', 'eta', 'gamma']})
        selection['kind'] = selected['kind']
    if method == 'mle':
        description = '比较接受域内的有限局部极大候选，选择原始对数似然最大的候选。'
        selection['description'] = description
        if selected:
            selection['log_likelihood'] = float(selected['ll'])
        likelihood = plot_chart(
            'profile-likelihood', '位置参数与剖面对数似然', '位置参数 γ', '剖面对数似然 ℓ',
            [plot_series('profile', '实际条件求值', [plot_point(
                p['gamma'], p['log_likelihood'], **p) for p in profiles]),
             plot_series('candidates', '有限极大候选', [plot_point(
                 p['gamma'], p['ll'], beta=p['beta'], eta=p['eta'], gamma=p['gamma'],
                 candidate_kind=p['kind']) for p in candidates], role='candidate', kind='scatter')],
            description='各点来自本次位置扫描与精化的条件求值；按 γ 排列展示函数形态，不表示迭代顺序。',
            selected=[plot_point(selected['gamma'], selected['ll'], label='最终选择')]
            if selected else [],
        )
        score = plot_chart(
            'location-score', '位置得分与极大值判据', '位置参数 γ', '位置得分 ∂ℓ/∂γ',
            [plot_series('score', '实际位置得分', [plot_point(
                p['gamma'], p['location_score'], **p) for p in profiles])],
            description='内点候选要求位置得分由正变负；γ=0 的候选按边界条件接受。',
            references=[dict(axis='y', value=0., label='位置得分 = 0')],
            selected=[plot_point(selected['gamma'], selected['location_score'], label='最终选择')]
            if selected else [],
        )
        charts = [likelihood, score]
        likelihood['formula'] = r'\hat\gamma=\arg\max_{\gamma\in\mathcal C}\ell(\beta^*(\gamma),\eta^*(\gamma),\gamma)'
        score['formula'] = r'\partial_\gamma\ell=0\quad\text{（内点：由正变负）}'
        recovery = [calculation_step('比较似然，确定位置', likelihood['formula'],
                                    [('γ̂', selected['gamma']), ('ℓ', selected['ll'])])] if selected else []
    else:
        description = ('接受 T₁²+T₂²≤10⁻⁸ 的候选；在最小残差 +10⁻¹² 内，'
                       '按距原启发式 β=2、γ=0.9·min(t) 最近的规则选根。')
        selection['description'] = description
        if selected:
            selection.update(objective=float(selected['objective']),
                             t1=float(selected['t1']), t2=float(selected['t2']),
                             approximate=selected['kind'] == 'boundary_residual_tolerance')
        residual = plot_chart(
            'weighted-location-equation', '加权位置方程的求根判据', '位置参数 γ', '位置方程残差 T₂',
            [plot_series('t2', '条件 T₁=0 下的 T₂', [plot_point(
                p['gamma'], p['t2'], **p) for p in profiles]),
             plot_series('roots', '接受候选', [plot_point(
                 p['gamma'], p['t2'], beta=p['beta'], eta=p['eta'], gamma=p['gamma'])
                 for p in candidates], role='candidate', kind='scatter')],
            description='本次实际条件求值；先求 T₁=0，再扫描和精化 T₂ 的根。零边界容差解单独标记。',
            references=[dict(axis='y', value=0., label='T₂ = 0')],
            selected=[plot_point(selected['gamma'], selected['t2'], label='最终选择')]
            if selected else [],
        )
        comparison = plot_chart(
            'candidate-residuals', '接受候选与最终选根', '候选位置参数 γ', '方程残差平方和 T₁²+T₂²',
            [plot_series('candidates', '接受候选', [plot_point(
                p['gamma'], p['objective'], beta=p['beta'], eta=p['eta'], gamma=p['gamma'],
                t1=p['t1'], t2=p['t2'], candidate_kind=p['kind'])
                for p in candidates], role='candidate', kind='scatter')],
            description=description,
            selected=[plot_point(selected['gamma'], selected['objective'], label='最终选择')]
            if selected else [],
        )
        charts = [residual, comparison]
        residual['formula'] = r'T_1(\beta,\gamma)=0,\qquad T_2(\beta,\gamma)=0'
        comparison['formula'] = r'T_1^2+T_2^2\leq10^{-8}'
        recovery = [calculation_step('联立加权方程，确定位置', residual['formula'],
                                    [('γ̂', selected['gamma']), ('T₁', selected['t1']), ('T₂', selected['t2'])])] if selected else []
    if selected:
        # The scalar root evaluations were recorded by the existing conditional
        # solver. Displaying them neither calls a second estimator nor changes it.
        shape_values = info.get('selected_shape_evaluations', [])
        closest = min(profiles, key=lambda p: abs(p['gamma'] - selected['gamma'])) if profiles else None
        shape_score = closest.get('shape_score') if method == 'mle' and closest else selected.get('t1')
        weight = '1' if method == 'mle' else 'J_2'
        shape_formula = (r'S_\beta=\frac{' + weight + r'}{\beta}+\overline{\ln d}'
                         r'-\frac{\sum d_i^\beta\ln d_i}{\sum d_i^\beta}=0,\quad d_i=t_i-\hat\gamma')
        if method == 'mle' and closest and closest.get('shape_at_lower_boundary'):
            shape_formula = r'\hat\beta=1,\quad S_\beta(1)\leq0\quad\text{（形状下界）}'
        if method == 'wmle' and selected['kind'] == 'boundary_residual_tolerance':
            shape_formula = r'\gamma=0,\quad T_1^2+T_2^2\leq10^{-8}\quad\text{（边界近似）}'
        if shape_values:
            curve_values = [p for p in shape_values if p.get('source') == 'diagnostic'] or shape_values
            charts.append(plot_chart(
                'conditional-shape-equation', '固定选中位置，求形状参数', '形状参数 β',
                '形状得分 Sβ' if method == 'mle' else '形状方程残差 T₁',
                [plot_series('shape-score', '同一形状方程的辅助采样',
                             [plot_point(p['beta'], p['score']) for p in curve_values], role='diagnostic'),
                 plot_series('solver-points', '本次求解计算点',
                             [plot_point(p['beta'], p['score'], evaluation=i+1)
                              for i, p in enumerate(shape_values) if p.get('source') == 'solver'], kind='scatter')],
                formula=shape_formula,
                description='固定 γ̂ 后的条件形状方程；β=1边界须按约束解释，不冒称零点。' if method == 'mle'
                else '固定 γ̂ 后求 T₁=0；该图与位置方程共同解释联立解。',
                references=[dict(axis='y', value=0., label='方程 = 0')],
                selected=[plot_point(selected['beta'], shape_score, label='最终形状参数')]
                if shape_score is not None else []))
        recovery.append(calculation_step('在该位置确定形状', shape_formula,
                                         [('β̂', selected['beta'])]))
        scale_formula = (r'\hat\eta=\left[\frac{\sum(t_i-\hat\gamma)^{\hat\beta}}{n'
                         + (r'J_1' if method == 'wmle' else '') + r'}\right]^{1/\hat\beta}')
        recovery.append(calculation_step('幂均值恢复尺度', scale_formula, [('η̂', selected['eta'])]))
    reading_frames = (_profile_reading_frames(method, data, selected, weights,
                      info.get('selected_shape_evaluations', []))
                      if data is not None and selected and
                      selected['kind'] != 'boundary_residual_tolerance' else [])
    scale_calculation = (power_scale_calculation(data, selected['beta'], selected['gamma'], selected['eta'],
                         normalizer=weights.get_weight_j1(len(data)) if method == 'wmle' else 1.0)
                         if data is not None and selected else None)
    weight_values = (dict(n=len(data), j1=float(weights.get_weight_j1(len(data))),
                         j2=float(weights.get_weight_j2(len(data))),
                         j3=float(weights.get_weight_j3(len(data), selected['beta'])),
                         shape=float(selected['beta']), j3_clamped=bool(selected['beta'] < .1 or selected['beta'] > 5))
                     if method == 'wmle' and data is not None and selected else None)
    equation_calculation = None
    if data is not None and selected:
        import numpy as np
        from scipy.special import logsumexp
        d = np.asarray(data, dtype=float) - selected['gamma']
        logs = np.log(d)
        beta = selected['beta']
        normalized = np.exp(beta*(logs-logs.max()))
        normalized /= normalized.sum()
        ratio = float(np.exp(logsumexp(beta*logs)-logsumexp((beta-1)*logs)))
        equation_calculation = dict(mean_log=float(logs.mean()), log_sum=float(logs.sum()),
            weighted_log_mean=float(normalized @ logs), inverse_mean=float(np.mean(1/d)),
            power_ratio=ratio,
            shape_weight=weight_values['j2'] if weight_values else 1.0,
            standardized_power_sum=float(np.exp(logsumexp(beta*(logs-np.log(selected['eta']))))))
    return dict(schema_version=1, method=method, criterion=dict(description=description),
                charts=charts, selection=selection, recovery=recovery,
                details=dict(solver_version=info['solver_version'], constraint=info['constraint'],
                             profile_evaluations=info['profile_evaluations'],
                             candidate_count=len(candidates),
                             support_boundary_limit=info.get('support_boundary_limit'),
                             boundary_limit_exceeds_selected=info.get('boundary_limit_exceeds_selected'),
                             selected_shape_evaluations=info.get('selected_shape_evaluations', []),
                             reading_frames=reading_frames,
                             scale_calculation=scale_calculation, weight_values=weight_values,
                             equation_calculation=equation_calculation,
                             evaluation_order='evaluation 字段为条件函数首次求值次序，非迭代次数'))

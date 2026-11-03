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


def profile_calculation(method, info, selected):
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
                             [plot_point(p['beta'], p['score']) for p in curve_values], role='diagnostic')],
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
    return dict(schema_version=1, method=method, criterion=dict(description=description),
                charts=charts, selection=selection, recovery=recovery,
                details=dict(solver_version=info['solver_version'], constraint=info['constraint'],
                             profile_evaluations=info['profile_evaluations'],
                             candidate_count=len(candidates),
                             support_boundary_limit=info.get('support_boundary_limit'),
                             boundary_limit_exceeds_selected=info.get('boundary_limit_exceeds_selected'),
                             selected_shape_evaluations=info.get('selected_shape_evaluations', []),
                             evaluation_order='evaluation 字段为条件函数首次求值次序，非迭代次数'))

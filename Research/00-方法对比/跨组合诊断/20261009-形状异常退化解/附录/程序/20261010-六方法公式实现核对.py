"""Audit report2 formulas and plot nodes against the thirteen frozen batches.

Compile the actual nested criterion functions from archived source without
running an estimator. Check saved paired-figure curves/points and WMLE grids,
then clarify the report's numerical procedures and calibration conventions.
Keep all samples, estimates, classification counts, and PNGs unchanged.
"""
import ast
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPORT = ROOT/'报告2：小样本情况下的明显异常估计.md'
QA = HERE/'20261010-六方法公式实现核验.json'
OUT = HERE/'20261010-六方法公式实现逐项.csv'
METHODS = ['lse', 'lre', 'mle', 'mdm', 'wmle', 'mmle']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bind(path, names, environment):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    for name in names:
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.Module(body=[copy.deepcopy(node)], type_ignores=[]), str(path), 'exec'), environment)
    return environment


REPLACEMENTS = [
    ('其中，ℓ为对数似然，dᵢ=x₍ᵢ₎−γ为样本距离。为画出似然随γ的变化，对尺度求导消去η，再由形状得分确定β，得到：',
     '其中，ℓ为对数似然，dᵢ=x₍ᵢ₎−γ为样本距离。为分析γ的影响，固定γ，在β>0、η>0下求条件最优值：先对尺度求导消去η，再由形状得分确定β，得到：'),
    ('MLE同时搜索形状、尺度和位置，以样本的对数似然作为准则：',
     'MLE以样本的对数似然作为准则，程序从多组固定起点联合搜索形状、尺度和位置，再比较收敛且β≥1的候选，返回似然较大的一个：'),
    (('其中，Uβ为形状得分，ȳ为yᵢ=ln dᵢ的均值。将β̂(γ)、η̂(γ)代回似然，便得到以γ为自变量的ℓₚ(γ)。',
      '其中，Uβ为除以n后的条件形状得分，ȳ为yᵢ=ln dᵢ的均值。将固定γ下求出的β̂(γ)、η̂(γ)代回似然，得到条件最优似然ℓₚ(γ)，用来比较原返回位置与其他候选位置的似然。'),
     '其中，Uβ为除以n后的条件形状得分，ȳ为yᵢ=ln dᵢ的均值。将固定γ下求出的β̂(γ)、η̂(γ)代回似然，得到条件最优似然ℓₚ(γ)，用来比较不同位置的似然与条件形状。'),
    (' g(\\gamma)=\\frac{d\\sigma[\\hat\\beta(\\gamma),\\gamma]}{d\\gamma}=\\delta.',
     ' g(\\gamma)\\approx\\frac{d\\sigma[\\hat\\beta(\\gamma),\\gamma]}{d\\gamma},\\qquad g(\\gamma)=\\delta.'),
    ('其中，ηᵢ为逐点伪尺度，σ为其标准差，g为梯度，此处pᵢ=(i−0.3)/(n+0.4)、δ=0.20。尺度估计取伪尺度的均值。梯度确定位置后，形状由该位置下伪尺度标准差的最低点确定。',
     '其中，ηᵢ为逐点伪尺度，σ为以n−1作分母的样本标准差，此处pᵢ=(i−0.3)/(n+0.4)、δ=0.20。图中的g按程序作有限差分：内部用中心差分，边界用单边差分。若g(0)≥δ，取γ=0；否则由右端探测建立区间，用Brent法寻找阈值交点，未建立区间时进入右端回退。返回位置下的形状使伪尺度标准差最小，尺度取伪尺度的均值。'),
    ('其中，T₁、T₂为方程残差，J₂、J₃为校准系数。两条零残差曲线的交点同时满足两式。令T₁[β̂(γ),γ]=0，再将β̂(γ)代入T₂，得到以γ为自变量的残差T₂[β̂(γ),γ]；其零点就是联合交点。',
     '其中，T₁、T₂为方程残差，J₂、J₃为存档程序使用的校准系数。J₃在形状0.1—5的表格内插值，超出时取边界列。两条零残差曲线的交点同时满足两式。为显示交点随位置的变化，沿T₁[β̂(γ),γ]=0代入T₂，得到T₂[β̂(γ),γ]；其零点就是联合交点。\n\n尺度按原加权公式计算：\n\n$$\n\\hat\\eta=\\left[\\frac{\\sum_i(x_{(i)}-\\hat\\gamma)^{\\hat\\beta}}{nJ_1(n)}\\right]^{1/\\hat\\beta}.\n$$\n\nJ₁为尺度校准系数，取值同样来自存档程序。'),
    ('得分曲线与零线的交点确定形状。比较完整样本、删点后的样本和删点后再作最小值平移的样本，可分别显示样本集中、删点和平移的作用。',
     '程序从β=1作固定点迭代求解该方程；迭代收敛到的形状对应得分曲线与零线的交点。尺度使用保留的n−1个观测计算：\n\n$$\n\\hat\\eta=\\left[\\frac1{n-1}\\sum_{i=2}^n d_i^{\\hat\\beta}\\right]^{1/\\hat\\beta}.\n$$\n\n比较完整样本、删点后的样本和删点后再作最小值平移的样本，可分别显示样本集中、删点和平移的作用。'),
    ('这些规则决定了样本扰动进入估计的方式，参数范围也影响异常频率。例如，MDM的形状搜索上界为15，限制了β=5时的大形状输出。因此，图2中的频率差异同时反映样本条件、方法准则和实现范围。',
     '这些规则决定了样本扰动进入估计的方式，搜索范围也影响异常频率。本批MDM的形状搜索上界为15，WMLE为10；β=5时的高估判据为β̂≥15，这两种程序的成功返回值达不到该界限。因此，图1中的方法频率差异同时反映样本条件、方法准则和实现范围。'),
]


def main():
    previous_path = HERE/'20261010-LRE相关系数判据核验.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8'))
    sources = dict(previous['source_sha256'])
    catalog_path = ROOT/'跨组合汇总/程序/20261007-新增五组合/13组合取数.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))['sources']
    pairs_path = HERE/'20261010-配对图参照线精简核验.json'
    pairs = json.loads(pairs_path.read_text(encoding='utf-8'))['pairs']
    curve_path = HERE/'20261010-参照线精简图数据.csv'
    rho_path = HERE/'20261010-LRE相关系数曲线.csv'
    grid_path = HERE/'20261010-参照线精简WMLE网格.npz'
    fixed_path = HERE/'20261010-异常分流核验.json'
    fixed_curve_path = HERE/'20261010-异常分流图数据.csv'
    fixed = json.loads(fixed_path.read_text(encoding='utf-8'))['conditional_example']
    sources.update({str(p):digest(p) for p in
                    [previous_path, catalog_path, pairs_path, curve_path, rho_path, grid_path,
                     fixed_path, fixed_curve_path, Path(__file__)]})
    snapshots, inventory, groups, matrices = {}, [], {}, {}
    for entry in catalog:
        program = Path(entry['program'])
        base = program if program.name == '程序' else program.parent
        snapshots[entry['combination']] = base/'依赖快照/python'
        matrix_path = base/('中间数据/matrix.json' if program.name=='程序' else '完整矩阵/数据/matrix.json')
        sources[str(matrix_path)] = digest(matrix_path)
        matrices[entry['combination']] = json.loads(matrix_path.read_text(encoding='utf-8'))
        for method in METHODS:
            path = snapshots[entry['combination']]/'methods'/f'{method}.py'
            value = digest(path)
            sources[str(path)] = value
            inventory.append(dict(combination=entry['combination'], method=method, path=str(path), sha256=value))
            groups.setdefault(method, set()).add(value)
        for path in [snapshots[entry['combination']]/'base.py',
                     snapshots[entry['combination']]/'methods/j3_weights.tsv']:
            sources[str(path)] = digest(path)
    assert len(inventory) == 78
    assert {key:len(values) for key,values in groups.items()} == dict(lse=1,lre=2,mle=1,mdm=1,wmle=1,mmle=1)
    assert all(digest(p) == value for p,value in sources.items())
    protected = {str(p):digest(p) for p in (HERE.parents[1]/'图片').glob('*.png')}
    before = REPORT.read_text(encoding='utf-8')
    with curve_path.open(encoding='utf-8-sig', newline='') as handle:
        curves = list(csv.DictReader(handle))
    with rho_path.open(encoding='utf-8-sig', newline='') as handle:
        rho_curves = list(csv.DictReader(handle))
    with fixed_curve_path.open(encoding='utf-8-sig', newline='') as handle:
        fixed_curves = list(csv.DictReader(handle))
    grids = np.load(grid_path)
    checks, grid_checks, source_functions, modules = [], [], {}, {}

    def module(path, method):
        key = (method, digest(path))
        if key not in modules:
            sys.path.insert(0, str(path.parent.parent))
            modules[key] = load(path, 'frozen_audit_'+method+'_'+key[1][:10])
        return modules[key]

    def check(example, role, kind, expected, observed, tolerance=2e-10):
        error = float(abs(float(expected)-float(observed)))
        limit = tolerance*(1+abs(float(expected)))
        assert error <= limit, (example, role, kind, expected, observed, error, limit)
        checks.append(dict(example=example, role=role, check=kind, expected=float(expected),
                           observed=float(observed), absolute_error=error, tolerance=limit))

    for label, pair in pairs.items():
        for role in ['normal', 'abnormal']:
            obj = pair[role]
            method = obj['method'].lower()
            if method.startswith('mdm'): method = 'mdm'
            path = snapshots[obj['combination']]/'methods'/f'{method}.py'
            x, n, g = np.asarray(obj['values']), obj['n'], obj['gamma_hat']
            archived_sample = next(s for s in matrices[obj['combination']]['samples'] if (s['n'],s['id'])==(n,obj['group']))
            assert np.array_equal(x,np.sort(archived_sample['values'])), (label,role,'sample provenance')
            beta, eta = obj['beta_hat'], obj['eta_hat']
            rows = [r for r in curves if r['example'] == label and r['role'] == obj['role']]
            assert rows, (label, role, 'missing saved plot nodes')
            check_start = len(checks)
            env = dict(np=np, n=n, arr=x, t=x, t_min=x[0], offset=.2,
                       minimize_scalar=minimize_scalar)
            for r in rows:
                if r['gamma_ratio']:
                    check(label,role,'position_normalization',float(r['gamma_ratio']),float(r['gamma'])/obj['gamma_true'])
                if r['panel']=='distance_estimated':
                    check(label,role,'normalized_distance',float(r['distance_ratio']),
                          (x[int(float(r['rank']))-1]-g)/obj['eta_true'])

            if method in ['lse','lre']:
                fit = [r for r in rows if r['panel'] == 'fit_estimated']
                assert fit and any(r['panel']=='criterion' for r in rows), (label, role)
                z = np.asarray([float(r['horizontal' if method == 'lse' else 'vertical']) for r in fit])
                if method == 'lse':
                    reference = module(path, method).log_weibull_order_stat_means(n)
                    check(label,role,'frozen_reference',0,np.max(np.abs(z-reference)))
                    env.update(X=z, x_bar=z.mean(), sxx=np.sum((z-z.mean())**2))
                    bind(path,['white_fit'],env)
                    slope, intercept, f_value = env['white_fit'](g)
                    check(label,role,'inverse_slope_shape',beta,1/slope,2e-5)
                    check(label,role,'intercept_scale',eta,np.exp(intercept),2e-5)
                    for r in fit:
                        i=int(float(r['rank']))-1
                        check(label,role,'normalized_log_distance',float(r['vertical']),np.log((x[i]-g)/obj['eta_true']))
                        check(label,role,'fitted_line',float(r['fitted']),intercept-np.log(obj['eta_true'])+slope*z[i])
                else:
                    entry = next(e for e in catalog if e['combination'] == obj['combination'])
                    ranks = np.arange(1,n+1)
                    p = (ranks-.3)/(n+.4) if entry['protocol']=='historical-eight' else ((ranks-3/8)/(n+1/4) if n<=10 else (ranks-.5)/n)
                    reference = np.log(-np.log1p(-p))
                    check(label,role,'frozen_plotting_positions',0,np.max(np.abs(z-reference)))
                    y=np.log(x-g);yc=y-y.mean();zc=z-z.mean()
                    slope=float(yc@zc/(yc@yc))
                    intercept=float(z.mean()-slope*y.mean())
                    check(label,role,'direct_slope_shape',beta,slope,2e-5)
                    check(label,role,'reverse_intercept_scale',eta,np.exp(-intercept/slope),2e-5)
                    for r in fit:
                        i=int(float(r['rank']))-1
                        check(label,role,'normalized_log_distance',float(r['horizontal']),y[i]-np.log(obj['eta_true']))
                        check(label,role,'fitted_line',float(r['fitted']),intercept+slope*y[i])
                    if entry['protocol']=='historical-eight':
                        env.update(y=z)
                        bind(path,['negative_r_squared'],env)
                        actual = lambda gamma: np.sqrt(-env['negative_r_squared'](gamma))
                        source_functions[str(path)] = ['negative_r_squared']
                    else:
                        env.update(relative_excess=(x-x[0])/x[0], y_centered=z-z.mean(), y_ss=np.sum((z-z.mean())**2))
                        bind(path,['negative_correlation'],env)
                        actual = lambda gamma: -env['negative_correlation'](np.log((x[0]-gamma)/x[0]))
                        source_functions[str(path)] = ['negative_correlation']
                for r in [r for r in rows if r['panel']=='criterion']:
                    gamma = float(r['gamma'])
                    if method=='lse':
                        slope,_,f_value = env['white_fit'](gamma)
                        check(label,role,'curve_shape',float(r['beta']),1/slope)
                        check(label,role,'curve_1_minus_R2',float(r['loss']),(n-2)/(n-1)/f_value)
                    else:
                        rr = next(q for q in rho_curves if q['example']==label and q['role']==obj['role'] and float(q['gamma'])==gamma)
                        check(label,role,'curve_rho_from_source',float(rr['rho']),actual(gamma))
                        y=np.log(x-gamma);yc=y-y.mean();zc=z-z.mean()
                        check(label,role,'curve_shape',float(r['beta']),yc@zc/(yc@yc))
                if method=='lse': source_functions[str(path)] = ['white_fit']

            elif method=='mle':
                bind(path,['neg_log_likelihood'],env)
                source_functions[str(path)] = ['neg_log_likelihood']
                profile = [r for r in rows if r['panel']=='profile']
                assert profile, (label, role, 'missing conditional likelihood nodes')
                for r in profile:
                    gamma, b = float(r['gamma']), float(r['beta'])
                    logs = np.log(x-gamma)
                    scale = np.exp((logsumexp(b*logs)-np.log(n))/b)
                    ll = -env['neg_log_likelihood']([b,scale,gamma])
                    check(label,role,'curve_likelihood',float(r['ll_difference']),ll-obj['at_true']['ll'])
                    weights = np.exp(b*(logs-logs.max())); weights /= weights.sum()
                    check(label,role,'conditional_shape_score',0,1/b+logs.mean()-weights@logs)
                check(label,role,'archived_joint_likelihood',obj['at_original']['ll'],
                      -env['neg_log_likelihood']([beta,eta,g]),2e-5)

            elif method=='mdm':
                assert any(r['panel']=='gradient' for r in rows) and any(r['panel']=='conditional_sigma' for r in rows)
                p = (np.arange(1,n+1)-.3)/(n+.4)
                env.update(neg_ln_1_minus_F=-np.log(1-p), beta_sigma_cache={},profile_gradient_cache={})
                names = ['calculate_eta_std','find_best_beta_for_gamma','profile_sigma','profile_gradient',
                         'find_right_anchor','fit_right_edge_root']
                bind(path,names,env);source_functions[str(path)]=names
                for r in rows:
                    if r['panel'] in ['gradient','right_anchor']:
                        gamma = float(r['gamma'])
                        tolerance = 8e-5 if r['panel']=='right_anchor' else 2e-7
                        check(label,role,'finite_gradient_'+r['panel'],float(r['gradient']),env['profile_gradient'](gamma),tolerance)
                    elif r['panel']=='conditional_sigma':
                        check(label,role,'pseudo_scale_sample_sd',float(r['sigma_ratio']),
                              env['calculate_eta_std'](float(r['beta']),g,x)/obj['eta_true'])
                    elif r['panel'].startswith('pseudo_scale_'):
                        b=obj['beta_true'] if r['panel']=='pseudo_scale_true_beta' else beta
                        i=int(float(r['rank']))-1
                        check(label,role,'normalized_pseudo_scale',float(r['scale_ratio']),
                              (x[i]-g)/env['neg_ln_1_minus_F'][i]**(1/b)/obj['eta_true'])
                b,_ = env['find_best_beta_for_gamma'](g)
                check(label,role,'conditional_shape',beta,b,2e-5)
                check(label,role,'mean_pseudo_scale',eta,np.mean((x-g)/env['neg_ln_1_minus_F']**(1/b)),2e-5)
                if obj['root_solver']=='right_edge_fit':
                    anchor,gradient = env['find_right_anchor']()
                    endpoint = env['fit_right_edge_root'](anchor,gradient)['gamma']
                    check(label,role,'right_edge_position',g,endpoint)
                    assert gradient < .2

            elif method=='wmle':
                assert any(r['panel']=='shape_zero_branch' for r in rows)
                weights_module = module(path,method)
                env.update(x_min=x[0],w2=weights_module.get_weight_j2(n),
                           SHAPE_UPPER=weights_module.SHAPE_UPPER,get_weight_j3=weights_module.get_weight_j3)
                bind(path,['wmle_objective'],env);source_functions[str(path)]=['wmle_objective']
                logs=np.log(x-g); w=np.exp(beta*(logs-logs.max()));w/=w.sum()
                t1=env['w2']/beta+logs.mean()-w@logs
                t2=np.mean(1/(x-g))*np.exp(logsumexp(beta*logs)-logsumexp((beta-1)*logs))-weights_module.get_weight_j3(n,beta)
                check(label,role,'joint_objective',t1*t1+t2*t2,env['wmle_objective']([beta,g]))
                scale=np.exp((logsumexp(beta*logs)-np.log(n*weights_module.get_weight_j1(n)))/beta)
                check(label,role,'J1_scale_correction',eta,scale,2e-5)
                for r in [r for r in rows if r['panel']=='shape_zero_branch']:
                    gamma,b,residual=float(r['gamma']),float(r['beta']),float(r['t2'])
                    assert 0<b<weights_module.SHAPE_UPPER
                    check(label,role,'conditional_branch_objective',residual**2,env['wmle_objective']([b,gamma]))
                gs,bs=[grids[label+'_'+obj['role']+'_'+key] for key in ['gamma','beta']]
                distances=x[None,:]-gs[:,None]
                powers=distances[:,None,:]**bs[None,:,None]
                logd=np.log(distances)
                T1=env['w2']/bs[None,:]+logd.mean(axis=1)[:,None]-(powers*logd[:,None,:]).sum(axis=2)/powers.sum(axis=2)
                T2=np.mean(1/distances,axis=1)[:,None]*powers.sum(axis=2)/(distances[:,None,:]**(bs[None,:,None]-1)).sum(axis=2)-np.array([weights_module.get_weight_j3(n,float(b)) for b in bs])[None,:]
                for key,actual_grid in [('T1',T1),('T2',T2)]:
                    expected_grid=grids[label+'_'+obj['role']+'_'+key]
                    error=float(np.max(np.abs(expected_grid-actual_grid)))
                    assert error<1e-10
                    grid_checks.append(dict(example=label,role=role,quantity=key,cells=int(actual_grid.size),max_absolute_error=error))
                assert weights_module.get_weight_j3(n,5.31)==weights_module.get_weight_j3(n,5)

            else:
                assert method=='mmle'
                assert {r['panel'] for r in rows if r['panel'].startswith('score_')} == {'score_complete_true','score_retained_true','score_retained_shifted'}
                retained=x[1:]
                logs=np.log(retained-g);q=n-1
                w=np.exp(beta*(logs-logs.max()));w/=w.sum()
                mean_weighted=float(w@logs)
                # Execute the actual archived next_beta expression, then verify
                # its fixed point is the normalized shape-score zero.
                tree=ast.parse(path.read_text(encoding='utf-8-sig'))
                node=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign)
                          and any(isinstance(t,ast.Name) and t.id=='next_beta' for t in n.targets))
                iteration_env=dict(float=float,np=np,q=q,beta=beta,logs=logs,denominator=q*mean_weighted)
                next_beta=eval(compile(ast.Expression(copy.deepcopy(node.value)),str(path),'eval'),iteration_env)
                check(label,role,'fixed_point_score_identity',next_beta-beta,
                      beta*(1/beta+logs.mean()-mean_weighted)/mean_weighted)
                check(label,role,'retained_power_scale',eta,
                      np.exp((logsumexp(beta*logs)-np.log(q))/beta),2e-5)
                for r in [r for r in rows if r['panel'].startswith('score_')]:
                    stage=r['panel'][6:]
                    values=x if stage=='complete_true' else retained
                    gamma=x[0] if stage=='retained_shifted' else obj['gamma_true']
                    b=float(r['beta']); logv=np.log(values-gamma)
                    w=np.exp(b*(logv-logv.max()));w/=w.sum()
                    check(label,role,'score_curve_'+stage,float(r['score']),1/b+logv.mean()-w@logv)
                for r in [r for r in rows if r['panel'].startswith('log_distance_')]:
                    gamma=g if r['panel']=='log_distance_retained_shifted' else obj['gamma_true']
                    check(label,role,'normalized_log_distance',float(r['log_distance']),
                          np.log((x[int(float(r['rank']))-1]-gamma)/obj['eta_true']))
                source_functions[str(path)]=['MMLE.run fixed-point update and retained-sample scale']
            assert len(checks)>check_start, (label, role, 'no checks executed')
        print('checked',label)

    assert {r['example'] for r in checks}==set(pairs) and len(pairs)==16
    assert any(r['check']=='curve_likelihood' for r in checks)

    # Figure24 uses the same frozen regression coordinates and MLE score,
    # with the true location supplied for two archived samples.
    for obj in fixed:
        x=np.asarray(obj['values']);n=len(x);g=500.;label='fixed_gamma_'+str(obj['group'])
        source_sample=next(s for s in matrices['W(5,1000,500)']['samples'] if (s['n'],s['id'])==(n,obj['group']))
        assert np.array_equal(x,np.sort(source_sample['values']))
        y=np.log(x-g);yc=y-y.mean()
        for method in ['lse','lre']:
            path=snapshots['W(5,1000,500)']/'methods'/f'{method}.py'
            z=(module(path,'lse').log_weibull_order_stat_means(n) if method=='lse'
               else np.log(-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4))))
            zc=z-z.mean()
            env=dict(np=np,n=n,t=x,X=z,x_bar=z.mean(),sxx=zc@zc)
            if method=='lse':
                bind(path,['white_fit'],env)
                slope,_,_=env['white_fit'](g);b=1/slope
            else:
                b=yc@zc/(yc@yc)
            check(label,'fixed_true','shape_'+method,obj['fits'][method.upper()]['beta'],b)
            rows=[r for r in fixed_curves if r['figure']=='fixed_gamma_'+method.upper() and int(r['group'])==obj['group']]
            assert len(rows)==n
            for r in rows:
                i=int(r['point'])-1
                xx,yy,fit=(zc[i],yc[i],zc[i]/b) if method=='lse' else (yc[i],zc[i],yc[i]*b)
                for key,value in [('x',xx),('y',yy),('fitted_y',fit)]:
                    check(label,'fixed_true',method+'_'+key,float(r[key]),value)
        rows=[r for r in fixed_curves if r['figure']=='fixed_gamma_MLE' and int(r['group'])==obj['group']]
        assert rows
        for r in rows:
            b=float(r['beta']);w=np.exp(b*(y-y.max()));w/=w.sum()
            check(label,'fixed_true','normalized_MLE_score',float(r['shape_score']),1/b+y.mean()-w@y)
        b=obj['fits']['MLE']['beta'];w=np.exp(b*(y-y.max()));w/=w.sum()
        check(label,'fixed_true','MLE_score_zero',0,1/b+y.mean()-w@y)
        check(label,'fixed_true','shape_lower_bound',obj['beta_lower_bound'],1/(y.max()-y.mean()))
    revised=before
    for old,new in REPLACEMENTS:
        matches=[value for value in ([old] if isinstance(old,str) else old) if value in revised]
        if matches:
            assert len(matches)==1 and revised.count(matches[0])==1
            revised=revised.replace(matches[0],new,1)
        else:
            assert new in revised
    assert before.split('## 2',1)[0]==revised.split('## 2',1)[0]
    tables=lambda t:re.findall(r'^\|[^\n]*(?:\n\|[^\n]*)*',t,flags=re.M)
    assert tables(before)==tables(revised)
    assert re.findall(r'!\[[^\]]*\]\([^\n]*\)',before)==re.findall(r'!\[[^\]]*\]\([^\n]*\)',revised)
    assert all(digest(p)==value for p,value in sources.items())
    assert all(digest(p)==value for p,value in protected.items())
    REPORT.write_text(revised,encoding='utf-8')
    with OUT.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(checks[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(checks)
    output=dict(scope='Report2; 13 frozen combinations, six methods, 16 pairs/32 saved samples and two fixed-location samples.',
                source_inventory=inventory, unique_versions={k:len(v) for k,v in groups.items()},
                actual_source_functions=source_functions, source_sha256=sources,sources_unchanged=True,
                checks=len(checks),checks_by_kind={k:sum(r['check']==k for r in checks) for k in sorted({r['check'] for r in checks})},
                wmle_grid_checks=grid_checks,all_checks_passed=True,
                findings=['LSE F and 1-R2 are equivalent; reference means and inverse slope agree.',
                          'Both LRE versions agree with positive rho; Bernard uses rho squared, Park uses rho.',
                          'MLE diagram profiles positive beta/eta at fixed gamma; original solver searches jointly and accepts only converged beta>=1. Profile segments below one describe the conditional criterion, not accepted archived estimates.',
                          'MDM curve uses archived finite differences, sample SD and exact fallback branch; explain the numerical derivative explicitly.',
                          'WMLE T1/T2 agree; explain J3 table clamping and include J1 in scale recovery.',
                          'MMLE score agrees with the archived fixed-point equation; explain actual iteration and retained n-1 scale.',
                          'MDM upper 15 and WMLE upper 10 prevent beta=5 estimates from reaching the threefold high threshold.'],
                protected_png_sha256=protected,all_pngs_unchanged=True,
                original_samples_estimates_and_frequencies_unchanged=True,chapter1_and_all_tables_unchanged=True,
                no_resampling=True,no_estimator_run_calls=True,
                report_replacements=[dict(before=a,after=b) for a,b in REPLACEMENTS],
                report_sha256=digest(REPORT),check_csv_sha256=digest(OUT))
    QA.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS:',len(checks),'point checks;',sum(r['cells'] for r in grid_checks),
          'WMLE grid cells; 78 frozen method files; saved samples, estimates, counts and all PNGs unchanged.')


if __name__=='__main__':
    main()

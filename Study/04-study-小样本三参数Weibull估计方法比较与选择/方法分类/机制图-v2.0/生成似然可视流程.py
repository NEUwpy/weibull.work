"""完整三参数联合似然：真实数值等值面与同一目标的优化迭代。"""
from pathlib import Path
import itertools
import json
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import brentq, differential_evolution, minimize
from scipy.stats import weibull_min
from skimage.measure import marching_cubes
from 细图绘制 import Diagram

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / '07-似然估计路线-信息处理流程.drawio'
META = ROOT / '预览' / '07-联合似然数值核对.json'
W, H = 3000, 1540
BLUE, TEAL, ORANGE = '#78B5D3', '#3E9A91', '#EAA052'
GRAY, RED = '#738293', '#B6404A'
SEED, N = 7, 24
DATA = np.sort(2 + 3 * np.random.default_rng(SEED).weibull(2.5, N))
# Compact visualization window, not the unrestricted Weibull domain.
BOUNDS = np.array([[1.2, 4.2], [1.5, 4.2], [.7, 2.4]], dtype=float)
LOWER, SPAN = BOUNDS[:, 0], np.diff(BOUNDS, axis=1)[:, 0]
LEVELS = [.25, .60, .85]
GRID_N, MESH_STEP = 41, 2


def loglik(theta):
    beta, eta, gamma = np.asarray(theta, dtype=float)
    y = DATA - gamma
    if beta <= 0 or eta <= 0 or np.any(y <= 0):
        return -np.inf
    return float(N * np.log(beta) - N * beta * np.log(eta)
                 + (beta - 1) * np.log(y).sum() - np.sum((y / eta) ** beta))


def objective(theta):
    return -loglik(theta)


# Broad search, independent local starts, and a recorded path all optimize the
# same function. Numerical agreement does not prove globality or uniqueness.
de = differential_evolution(objective, BOUNDS, seed=24, tol=1e-11,
                            popsize=16, maxiter=1200, polish=True)
starts = [LOWER + SPAN * np.asarray(u) for u in
          [(.2, .2, .2), (.8, .7, .2), (.3, .5, .7), (.7, .3, .8), (.5, .5, .5)]]
local_results = [minimize(objective, p, bounds=BOUNDS, method='Nelder-Mead',
                          options={'xatol': 1e-10, 'fatol': 1e-11, 'maxiter': 2500})
                 for p in starts]
START = np.array([1.4, 3.8, 1.0])
path = [START.copy()]
path_result = minimize(objective, START, bounds=BOUNDS, method='Nelder-Mead',
                       callback=lambda p: path.append(p.copy()),
                       options={'xatol': 1e-10, 'fatol': 1e-11, 'maxiter': 2500})
path.append(path_result.x.copy())
best = min([de, path_result, *local_results], key=lambda r: r.fun)
THETA_STAR, ELL_STAR = best.x.copy(), loglik(best.x)

# Sample the actual full three-dimensional likelihood, without an ellipsoid fit.
axes = [np.linspace(a, b, GRID_N) for a, b in BOUNDS]
B, E, G = np.meshgrid(*axes, indexing='ij')
Y = DATA[:, None, None, None] - G
ELL = (N * np.log(B) - N * B * np.log(E)
       + (B - 1) * np.log(Y).sum(axis=0) - np.sum((Y / E) ** B, axis=0))
LOG_R = ELL - ELL_STAR

# Parallel projection of scaled parameter coordinates, recorded in the meta.
ORIGIN = np.array([1280., 1140.])
PROJECT = np.array([[850., -420., 0.], [-25.5, -178.5, -484.5]])
VIEW = np.cross(PROJECT[0], PROJECT[1]); VIEW /= np.linalg.norm(VIEW)
LIGHT = np.array([-.25, -.45, .86]); LIGHT /= np.linalg.norm(LIGHT)


def project_u(u):
    return ORIGIN + np.asarray(u) @ PROJECT.T


def project_theta(theta):
    return project_u((np.asarray(theta) - LOWER) / SPAN)


def shade(hexcolor, factor):
    rgb = [int(hexcolor[i:i+2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{int(np.clip(v * factor, 0, 255)):02X}' for v in rgb)


meshes, facets = [], []
for layer, (level, color, opacity) in enumerate(zip(LEVELS, [BLUE, TEAL, ORANGE], [.16, .32, .75])):
    verts, faces, _, _ = marching_cubes(LOG_R, level=np.log(level), step_size=MESH_STEP)
    # Marching cubes supplies topology and edge locations. Refine each crossing
    # against the actual likelihood along that grid edge, retaining the same
    # triangle budget while avoiding a coarse linear-interpolation value error.
    raw_u = verts / (GRID_N - 1)
    raw_errors = [loglik(LOWER + p * SPAN) - ELL_STAR - np.log(level) for p in raw_u]
    refined = verts.astype(float)
    for vertex in refined:
        distances = np.abs(vertex / MESH_STEP - np.rint(vertex / MESH_STEP))
        k = int(np.argmax(distances))
        if distances[k] < 1e-7:
            continue
        lo = np.floor(vertex[k] / MESH_STEP) * MESH_STEP
        hi = min(lo + MESH_STEP, GRID_N - 1)
        base = np.rint(vertex / MESH_STEP) * MESH_STEP

        def edge_residual(q):
            v = base.copy(); v[k] = q
            return loglik(LOWER + v / (GRID_N - 1) * SPAN) - ELL_STAR - np.log(level)

        vertex[:] = base
        vertex[k] = brentq(edge_residual, lo, hi, xtol=1e-12)
    u = refined / (GRID_N - 1)
    actual = LOWER + u * SPAN
    errors = np.array([loglik(t) - ELL_STAR - np.log(level) for t in actual])
    clipped = bool(np.any(np.isclose(u, 0)) or np.any(np.isclose(u, 1)))
    meshes.append({'relative_likelihood': level, 'faces': len(faces), 'vertices': len(verts),
                   'clipped_by_window': clipped,
                   'raw_max_abs_vertex_logR_interpolation_error': float(np.max(np.abs(raw_errors))),
                   'max_abs_vertex_logR_error_after_edge_refinement': float(np.max(np.abs(errors))),
                   'mean_abs_vertex_logR_error_after_edge_refinement': float(np.mean(np.abs(errors)))})
    for j, face in enumerate(faces):
        tri = u[face]
        normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        norm = np.linalg.norm(normal)
        illum = abs(float(np.dot(normal / norm, LIGHT))) if norm else 0.
        facets.append((float(np.dot(tri.mean(axis=0), VIEW)), layer, j,
                       project_u(tri), shade(color, .88 + .12 * illum), opacity))

d = Diagram('likelihood-joint-field-v20', '似然原理：完整三参数联合函数与最大化', W, H)
d.text('title', '似然原理｜构造整个联合似然，再在三参数空间中最大化', 40, 20, 2910, 70, size=42, bold=True)
d.text('core', r'固定样本 \(D\)；每个参数组合 \((\beta,\eta,\gamma)\) 对应一个联合似然值 \(L(\beta,\eta,\gamma;D)\)。', 45, 100, 2900, 60, size=31)
d.text('sample-scope', r'原理图使用同一组模拟样本，\(n=24\)；三根轴表示参数，颜色与等值面表示第四维——似然大小。', 45, 170, 2900, 55, size=28)
d.panel('data-panel', 30, 250, 600, 1110, fill='#F3F7FB')
d.panel('field-panel', 710, 250, 1670, 1110, fill='#F7F9FA')
d.panel('max-panel', 2460, 250, 510, 1110, fill='#F1F7F4')
d.text('data-title', '① L1 由固定样本构造', 50, 270, 560, 65, size=33, bold=True)
d.text('field-title', '② 完整三参数联合似然场', 735, 270, 1600, 65, size=34, bold=True)
d.text('max-title', '③ L2 联合最大化', 2480, 270, 470, 65, size=33, bold=True)

# Native editable faces ordered back to front, then cage/path/labels.
for _, layer, j, points, color, opacity in sorted(facets, key=lambda f: f[0]):
    d.polygon(f'likelihood-surface-{layer}-{j}', points.tolist(), fill=color,
              stroke='none', opacity=opacity, width=.4)
corners = list(itertools.product([0., 1.], repeat=3))
for i, a in enumerate(corners):
    for dim in range(3):
        if a[dim] == 0:
            b = list(a); b[dim] = 1.
            d.line(f'window-edge-{i}-{dim}', [project_u(a), project_u(b)],
                   color='#A4AFBA', width=1.6, dashed=True)
for i, name in enumerate([r'\(\beta\)',r'\(\eta\)',r'\(\gamma\)']):
    u = np.zeros(3); u[i] = 1.06
    head=project_u(u)
    d.line('parameter-axis-' + str(i), [ORIGIN, head], color=GRAY, width=3.5, arrow='block')
    ox,oy=[(-15,10),(-105,-60),(-95,-50)][i]
    d.text('parameter-axis-label-' + str(i), name, head[0]+ox,head[1]+oy,95,60, size=34, bold=True, align='center')
    p = project_u(np.eye(3)[i])
    dx, dy = [(-10,-45),(-95,30),(-95,15)][i]
    d.text('parameter-tick-' + str(i), rf'\({BOUNDS[i,1]:g}\)', p[0]+dx, p[1]+dy, 100, 45,
           size=25, color=GRAY, align='center')

# Select only actual callback points. Full unrounded history is retained below.
unique_path = [path[0]]
for p in path[1:]:
    if np.linalg.norm((p - unique_path[-1]) / SPAN) > 1e-7:
        unique_path.append(p)
selected = np.unique(np.rint(np.linspace(0, len(unique_path)-1, 20)).astype(int))
drawn_path = np.asarray([unique_path[i] for i in selected])
projected_path = project_theta(drawn_path)
d.line('actual-iteration-path', projected_path.tolist(), color=RED, width=4.7, arrow='block')
for i, p in enumerate(projected_path):
    d.box('iteration-point-' + str(i), '', p[0]-4, p[1]-4, 8, 8,
          fill=RED, color=RED, size=1, extra='shape=ellipse;')
p0 = projected_path[0]
d.box('iteration-start', '迭代起点', p0[0]-155, p0[1]-95, 190, 55, size=26, color=RED, fill='#FFFFFF')
d.line('iteration-start-leader',[p0+np.array([-30.,-40.]),p0],color=RED,width=2)
peak = project_theta(THETA_STAR)
d.line('peak-cross-h', [(peak[0]-13,peak[1]),(peak[0]+13,peak[1])], color=RED, width=5)
d.line('peak-cross-v', [(peak[0],peak[1]-13),(peak[0],peak[1]+13)], color=RED, width=5)
d.line('peak-callout', [peak, (1585, 475), (1745, 475)], color=RED, width=2.6)
d.box('peak-label', r'窗内数值极大点<br>\(R=1\)', 1740, 420, 340, 115,
      size=28, bold=True, color=RED, fill='#FFFFFF')
d.text('axis-origin',r'轴起点 \((1.2,1.5,0.7)\)',1325,1140,460,50,size=24,color=GRAY)
inner_points=np.vstack([face[3] for face in facets if face[1]==2])
inner_anchor=inner_points[np.argmax(inner_points[:,0])]
d.line('inner-surface-callout',[inner_anchor,(1790,762)],color='#AD6C20',width=2)
d.box('inner-surface-label',r'\(R=0.85\)',1790,730,285,65,size=27,color='#AD6C20',fill='#FFFFFF')

# L1 is deliberately secondary to the full joint field.
d.text('fixed-data', r'同一组完整、独立观测 \(D\)', 65, 365, 525, 60, size=29, bold=True)
d.text('sample-definition', r'样本 \(D=(x_1,\ldots,x_{24})\)<br>同一组数据贯穿整个参数场', 65, 430, 525, 105, size=28)
sx = lambda x: 85 + (x-2.3)/(7.05-2.3)*490
d.line('sample-axis', [(75, 655), (585, 655)], color=GRAY, width=2.6, arrow='block')
for i, x in enumerate(DATA):
    row = i % 3
    d.box('sample-point-' + str(i), '', sx(x)-4.5, 610-row*19, 9, 9,
          fill='#337695', color='#337695', size=1, extra='shape=ellipse;')
    d.line('sample-rug-' + str(i), [(sx(x), 648), (sx(x), 660)], color='#337695', width=2)
d.text('sample-min', rf'\(x_{{(1)}}={DATA.min():.3f}\)', 60, 680, 270, 55, size=27)
d.text('sample-x-axis', r'观测寿命 \(x\)', 340, 680, 250, 55, size=27, align='right')
d.box('joint-construction', r'\(L(\beta,\eta,\gamma;D)\)<br>\(=\displaystyle\prod_{i=1}^{n}f(x_i;\beta,\eta,\gamma)\)',
      65, 790, 530, 180, fill='#FFFFFF', color='#337695', size=31, bold=True)
d.text('density-small', r'\(f(x_i;\theta)=\dfrac{\beta}{\eta}\left(\dfrac{x_i-\gamma}{\eta}\right)^{\beta-1}\!\exp\!\left[-\left(\dfrac{x_i-\gamma}{\eta}\right)^\beta\right]\)',
       65, 995, 530, 150, size=25)
d.text('support', r'支持域：\(\beta>0,\eta>0,\gamma<x_{(1)}\)', 65, 1180, 530, 90, size=27, bold=True)
d.line('construct-to-field', [(645, 815), (695, 815)], color='#337695', width=5, arrow='block')

d.text('field-definition', r'同一面上的 \(R\) 相同；蓝 → 绿 → 橙表示联合似然增大', 755, 350, 1550, 60, size=29, bold=True)
d.text('window-bounds', r'有限参数窗 \(\mathcal W=[1.2,4.2]\times[1.5,4.2]\times[0.7,2.4]\)', 745, 1195, 1595, 60, size=29, align='center')
for i, (level, color) in enumerate(zip(LEVELS, [BLUE, TEAL, ORANGE])):
    x = 825 + i*470
    d.box('relative-level-chip-' + str(i), '', x, 1280, 58, 30, fill=color, color=color, size=1)
    d.text('relative-level-label-' + str(i), rf'\(R={level:g}\)', x+70, 1265, 320, 60, size=29)
d.line('field-to-maximum', [(2390, 815), (2445, 815)], color=TEAL, width=5, arrow='block')

d.box('max-principle', r'\(\theta_{\mathcal W}^{\star}\in\operatorname*{arg\,max}_{\theta\in\mathcal W}L(\theta;D)\)<br>等价于最大化 \(\ell(\theta)=\log L(\theta;D)\)',
      2480, 370, 470, 175, fill='#FFFFFF', color=TEAL, size=28, bold=True)
d.text('numerical-result-title', '图中窗内数值极大点', 2485, 585, 460, 55, size=28, bold=True)
d.box('numerical-result', rf'\(\beta^\star={THETA_STAR[0]:.4f}\)<br>\(\eta^\star={THETA_STAR[1]:.4f}\)<br>\(\gamma^\star={THETA_STAR[2]:.4f}\)<br>\(\ell^\star_{{\mathcal W}}={ELL_STAR:.4f}\)',
      2480, 655, 470, 240, fill='#FFFFFF', color=TEAL, size=29)
d.line('path-legend', [(2495, 955), (2570, 955)], color=RED, width=5, arrow='block')
d.text('path-legend-label', '同一目标的一次实际迭代', 2580, 925, 355, 65, size=27, color=RED)
d.text('path-numerics', '红点为记录的迭代点；连线显示参数在联合空间中的移动。', 2490, 1000, 445, 105, size=26)
d.box('window-limit', r'图中求解范围：\(\mathcal W\)<br>全参数域需另行核验<br>支持边界与有限最大值', 2480, 1155, 470, 155,
      fill='#FFFFFF', color=GRAY, size=27)
d.text('relative-definition', r'颜色只重标同一似然函数的大小：\(R(\theta)=\exp[\ell(\theta)-\ell^\star_{\mathcal W}]\)。三坐标经线性缩放；等值面由数值网格插值，两外层在参数窗处截断。',
       40, 1390, 2910, 70, size=27)
d.text('scope', '原理示意，非方法比较实验。相对似然不是参数概率；统计原则是联合最大化，优化器只是实现这一步的计算工具。',
       40, 1470, 2910, 55, size=26)
d.save(TARGET)

# Independent numerical and structural checks, retained for reproducibility.
scipy_ll = float(weibull_min.logpdf(DATA, c=THETA_STAR[0], scale=THETA_STAR[1], loc=THETA_STAR[2]).sum())
assert abs(scipy_ll - ELL_STAR) < 1e-10
assert DATA.min() > BOUNDS[2, 1]
assert np.all(THETA_STAR > LOWER) and np.all(THETA_STAR < BOUNDS[:, 1])
assert len(facets) <= 3000
assert np.max(ELL) <= ELL_STAR + 1e-8
assert abs(loglik(path_result.x) - ELL_STAR) < 1e-7
assert max(loglik(r.x) for r in local_results) <= ELL_STAR + 1e-8
path_values = [loglik(p) for p in path]
assert np.min(np.diff(path_values)) >= -1e-9
cells = ET.parse(TARGET).findall('.//mxCell')
ids = [c.get('id') for c in cells]
assert len(ids) == len(set(ids))
for cell in cells:
    if cell.get('edge') == '1':
        assert cell.get('source') in ids and cell.get('target') in ids
    if cell.get('vertex') == '1':
        geo = cell.find('mxGeometry')
        x, y, w, h = (float(geo.get(k, '0')) for k in ('x', 'y', 'width', 'height'))
        assert 0 <= x <= x+w <= W and 0 <= y <= y+h <= H, cell.get('id')
META.parent.mkdir(exist_ok=True)
META.write_text(json.dumps({
    'purpose': 'Full three-parameter Weibull joint likelihood; mechanism illustration, not comparative experiment.',
    'sample': {'numpy_seed': SEED, 'n': N, 'generating_beta_eta_gamma': [2.5, 3, 2], 'observations': DATA.tolist()},
    'parameter_order': ['beta', 'eta', 'gamma'], 'finite_parameter_window': BOUNDS.tolist(),
    'numerical_window_maximum': THETA_STAR.tolist(), 'loglik_at_maximum': ELL_STAR,
    'scipy_logpdf_error': scipy_ll - ELL_STAR,
    'maximum_claim': 'Highest numerical candidate in the finite window; not a proof of uniqueness or an unrestricted global MLE.',
    'relative_likelihood': 'exp(loglik(theta)-loglik(theta_star_window)); not a parameter probability, posterior, or calibrated confidence region.',
    'surface_grid': {'shape': list(LOG_R.shape), 'marching_cubes_step': MESH_STEP, 'total_triangles': len(facets),
       'edge_refinement': 'Each marching-cubes edge crossing refined with the actual loglik by Brent root-finding; triangle interiors remain a piecewise-planar approximation.', 'levels': meshes},
    'projection': {'normalized_parameters': '(theta-lower)/(upper-lower)', 'origin': ORIGIN.tolist(), 'matrix': PROJECT.tolist(), 'depth_view': VIEW.tolist()},
    'optimization_checks': {'differential_evolution': {'theta': de.x.tolist(), 'loglik': loglik(de.x), 'success': bool(de.success)},
       'independent_local_starts': [{'start': p.tolist(), 'theta': r.x.tolist(), 'loglik': loglik(r.x), 'success': bool(r.success)} for p, r in zip(starts, local_results)],
       'grid_maximum_loglik': float(ELL.max())},
    'actual_path': {'method': 'Nelder-Mead with the same finite bounds and log-likelihood objective',
       'start': START.tolist(), 'final': path_result.x.tolist(), 'success': bool(path_result.success),
       'callback_points_with_start_and_final': [p.tolist() for p in path], 'loglik_values': path_values,
       'drawn_callback_points': drawn_path.tolist(), 'path_line': 'Straight segments connect selected recorded iteration points; not a continuous trajectory.'},
    'scientific_boundary': 'In the unrestricted three-parameter Weibull family, beta<1 and gamma approaching the sample minimum may make likelihood unbounded. The plotted compact window excludes that boundary and has a continuous finite objective.',
    'checks': {'unique_ids': True, 'edge_endpoints': True, 'canvas_bounds': True, 'scipy_likelihood': True,
       'same_objective_path': True, 'nondecreasing_recorded_best_loglik': True, 'all_data_in_support': True},
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'generated {TARGET.name}: {len(cells)} cells, {len(facets)} native mesh triangles; '
      f'window maximum={THETA_STAR.tolist()}, loglik={ELL_STAR:.10f}; all checks pass')

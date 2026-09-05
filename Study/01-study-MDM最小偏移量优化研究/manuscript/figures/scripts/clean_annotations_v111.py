"""Export existing figure designs with repeated annotation text removed."""
from pathlib import Path
import hashlib
import json
import sys
import pandas as pd
from pandas.testing import assert_frame_equal
import make_submission_figures as plot

F = Path(__file__).resolve().parents[1]
NOTES = {
    'supp_fig_unseen_beta': 'Line: primary seed 42; shading: three-seed range',
    'supp_fig_quantile_rmse': 'Mean-normalized point: primary seed 42; error bars: three-seed range',
    'supp_fig_parameter_landscape': 'Outlined cells indicate deterioration (35 of 160 parameter combinations).',
    'supp_fig_z_only_learning_curve': 'Fixed confirmation set; descriptive only and not used for model selection.',
}
report = []
original_export = plot.export_figure

def export_without_note(fig, stem, folder, **kwargs):
    matches = [t for t in fig.findobj(match=plot.Text) if t.get_text() == NOTES[stem]]
    assert len(matches) == 1, (stem, len(matches))
    matches[0].remove()
    if stem == 'supp_fig_z_only_learning_curve':
        # Each series contains 40 parameter cells for one n, not four models.
        fig.axes[0].set_xlabel('每个样本量模型的训练样本数')
    original_export(fig, stem + '_v111', folder, **kwargs)
    report.append({'figure': stem, 'removed_annotation': NOTES[stem],
                   'axis_correction': 'Training samples per n model' if stem == 'supp_fig_z_only_learning_curve' else None})

def verify_source(df, name):
    """Reused plotting functions must reproduce the existing source tables."""
    old = pd.read_csv(F / 'data' / 'derived' / name)
    new = df.copy()
    for col in new.columns:
        if isinstance(new[col].dtype, pd.CategoricalDtype):
            new[col] = new[col].astype(str)
    assert_frame_equal(old, new.reset_index(drop=True), check_dtype=False,
                       check_exact=False, rtol=1e-12, atol=1e-12)

def hashes():
    return {str(p.relative_to(F)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (F / 'data').rglob('*') if p.is_file()}

before = hashes()
plot.export_figure = export_without_note
plot.save_source = verify_source
plot.parameter_landscape_data = lambda paths: pd.read_csv(F / 'data/derived/supp_parameter_landscape.csv')
plot.e10_mechanism_data = lambda paths: (None, None, None, pd.read_csv(F / 'data/derived/supp_z_only_learning_curve.csv'))
paths = plot.source_paths()
for draw in [plot.supplementary_unseen_beta, plot.supplementary_quantiles,
             plot.supplementary_parameter_landscape, plot.supplementary_z_only_learning_curve]:
    if len(sys.argv) > 1 and draw.__name__ not in sys.argv[1:]:
        continue
    draw(paths)
    print(draw.__name__, 'exported', flush=True)
assert before == hashes(), 'Source data changed'
if len(sys.argv) > 1:
    previous = json.loads((F / 'provenance/annotation-cleanup-v111.json').read_text(encoding='utf-8'))
    changed = {item['figure'] for item in report}
    report = [item for item in previous['figures'] if item['figure'] not in changed] + report
(F / 'provenance/annotation-cleanup-v111.json').write_text(json.dumps({
    'scope': 'Remove repeated annotation text; original data and plotting geometry retained',
    'figures': report, 'source_data_sha256': before,
}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

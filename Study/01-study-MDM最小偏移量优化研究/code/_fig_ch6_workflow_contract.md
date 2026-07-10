# Ch6 workflow figure contract

- **Core conclusion**: E3b uses only deployable sample information to predict a 26-point loss vector, selects `delta` by `argmin`, and reserves true selected-loss for offline evaluation.
- **Archetype**: single-panel schematic-led method figure.
- **Backend**: Python / matplotlib only.
- **Final size**: double-column width, approximately 183 mm × 82 mm.
- **Main lane**: lifetime sample → 13 observable features → vector-output MLP → 26 predicted losses → selected `delta`.
- **Offline lane**: raw 26-point MC loss labels fit the model; the selected `delta` is evaluated using true selected-loss and aggregated as `J1`.
- **Evidence hierarchy**: the figure explains method semantics; Table 5 remains the quantitative result authority; the former model-J1 bar chart is supplementary.
- **Excluded deployment inputs**: true `beta`, true `gamma/eta`, configuration ID, seed, `repeat_id`, and candidate `delta`.
- **Reviewer risks**: leakage of true parameters, confusion between E3a scalar and E3b vector input, confusion between predicted loss and true selected-loss, or reading offline labels as deployment inputs.
- **Exports**: editable SVG, PDF, and 300 dpi PNG.

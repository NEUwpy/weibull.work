"""Compare the frozen network with the B10 map; do not train or tune anything."""
import csv
import json
import numpy as np
import b10_feature_selector as s

FIGURE_LABELS = {
    50:['WMLE','MDM-0.1','WMLE','WMLE','WMLE','WMLE','LSE','WMLE'],
    20:['MDM-0.1','MDM-0.1','LRE(Park)','LRE(Park)','LRE(Park)','LSE','WMLE','WMLE'],
    15:['MDM-0.1','MDM-0.1','MDM-0.1','LRE(Park)','LRE(Park)','WMLE','WMLE','WMLE'],
    10:['LRE(Park)','LRE(Park)','LRE(Park)','LSE','WMLE','WMLE','WMLE','WMLE'],
    7:['LRE(Park)','LRE(Park)','LSE','WMLE','WMLE','WMLE','MLE','MLE'],
}


def main():
    data=s.load_data()
    manifest=json.loads((s.OUT/'manifest.json').read_text(encoding='utf-8'))
    assert s.sha(s.OUT/'dataset.npz')==manifest['dataset_sha256']
    for path,expected in manifest['source_hashes'].items():
        assert s.sha(s.STUDY/path)==expected
    test=s.subset(data,data['split']==2)
    with (s.OUT/'test_predictions.csv').open(encoding='utf-8-sig',newline='') as f:
        records=list(csv.DictReader(f))
    assert [r['hash'] for r in records]==test['hash'].tolist()
    predictions=np.array([[float(r[m+'_predicted_mse']) for m in s.METHODS] for r in records])
    common=test['valid'].all(axis=1)
    errors=test['e'][common]
    cells=test['cell'][common]
    pred=predictions[common]
    choice=pred.argmin(axis=1)
    full_map=s.training_rules(data,np.ones(len(data['x']),bool),test)['truth_table_reference'][common]
    train_map=s.training_rules(data,data['split']==0,test)['truth_table_reference'][common]
    map_choice=full_map.argmin(axis=1)
    train_choice=train_map.argmin(axis=1)
    hindsight=np.argmin(errors**2,axis=1)
    strategies={'report_map':map_choice,'training_only_map':train_choice,'network':choice,'hindsight_reference':hindsight}
    selected={name:errors[np.arange(len(errors)),ch] for name,ch in strategies.items()}
    summaries={name:s.equal_summary(e,cells) for name,e in selected.items()}
    original_evaluation=json.loads((s.OUT/'evaluation.json').read_text(encoding='utf-8'))
    np.testing.assert_allclose(summaries['network']['rmse'],original_evaluation['metrics']['network']['common']['rmse'],rtol=1e-12)
    np.testing.assert_allclose(summaries['training_only_map']['rmse'],original_evaluation['metrics']['truth_table_reference']['common']['rmse'],rtol=1e-12)
    table=[]
    for c in np.unique(cells):
        mask=cells==c
        n=int(test['n'][common][mask][0]);beta=float(test['beta'][common][mask][0])
        map_m=int(map_choice[mask][0]);predicted=int(pred[mask].mean(axis=0).argmin())
        expected=FIGURE_LABELS[n][s.CONFIG['beta'].index(beta)]
        assert s.METHODS[map_m]==expected, (n,beta,s.METHODS[map_m],expected)
        order=np.argsort(full_map[mask][0])
        gap=(np.sqrt(full_map[mask][0,order[1]]/full_map[mask][0,order[0]])-1)*100
        nr=s.summarize_standard_errors(selected['network'][mask])['rmse']
        mr=s.summarize_standard_errors(selected['report_map'][mask])['rmse']
        aggregate_regret=(np.sqrt(full_map[mask][0,predicted]/full_map[mask][0,map_m])-1)*100
        table.append(dict(cell=str(c),n=n,beta=beta,test_common_count=int(mask.sum()),
            report_map_method=s.METHODS[map_m],predicted_average_risk_method=s.METHODS[predicted],
            mean_risk_map_match=bool(predicted==map_m),
            map_method_in_average_predicted_top2=bool(map_m in pred[mask].mean(axis=0).argsort()[:2]),
            report_map_second_gap_pct=float(gap),
            average_risk_choice_actual_map_regret_pct=float(aggregate_regret),
            report_map_test_rmse=float(mr),network_test_rmse=float(nr),
            network_improvement_vs_report_map_pct=float((1-nr/mr)*100)))
    result=dict(common_test_rows=len(errors),same_metric='R=0.90; beta*n cells equally weighted; all seven methods valid',
        report_map_rebuilt_from='all 1200 rows per cell, matching source figure',
        source_figure_sha256=s.sha(s.STUDY/'reviewbyhtml/方法对比-v1.0/assets/v04_06_寿命目标及候选差距.png'),
        rebuilt_grid_matches_transcribed_figure=True,
        original_map_contains_test_labels=True,training_only_map_contains_test_labels=False,
        network_retrained=False,
        rmse={k:v['rmse'] for k,v in summaries.items()},
        improvement_vs_report_map_pct=(1-summaries['network']['rmse']/summaries['report_map']['rmse'])*100,
        improvement_vs_training_only_map_pct=(1-summaries['network']['rmse']/summaries['training_only_map']['rmse'])*100,
        improvement_vs_training_only_map_ci95=s.bootstrap_delta(selected['training_only_map'],selected['network'],cells),
        network_actual_best_sample_hits=int(np.sum(choice==hindsight)),
        network_actual_best_sample_rate=float(np.mean(choice==hindsight)),
        map_actual_best_sample_hits=int(np.sum(map_choice==hindsight)),
        map_actual_best_sample_rate=float(np.mean(map_choice==hindsight)),
        network_choice_matches_map_sample_rate=float(np.mean(choice==map_choice)),
        grid_mean_risk_map_hits=sum(r['mean_risk_map_match'] for r in table),
        grid_mean_risk_top2_map_hits=sum(r['map_method_in_average_predicted_top2'] for r in table),
        grid_total=len(table),
        cells_network_lower_rmse=sum(r['network_test_rmse']<r['report_map_test_rmse'] for r in table),
        median_map_second_gap_pct=float(np.median([r['report_map_second_gap_pct'] for r in table])),
        average_risk_choice_map_regret_pct_quantiles=np.percentile(
            [r['average_risk_choice_actual_map_regret_pct'] for r in table],[0,50,90,100]).tolist(),
        warning='Original-map comparison is descriptive because the original map uses test outcomes; training-only map is the independent reference.')
    s.csv_write(s.OUT/'map_comparison_cells.csv',table)
    s.json_write(s.OUT/'map_comparison.json',result)
    ci=result['improvement_vs_training_only_map_ci95']
    text=f'''# B10性能地图与特征网络：对照补充 v1.0

2026-10-24。冻结原网络，不重新训练、不根据本次比较调参。由存档逐行误差重建原B10地图，40格冠军与报告下图a一致。

**网络目前能选预测风险最小的方法，并不能保证每组都选到事后真实误差最小的方法。** “是否复现地图冠军”和“逐样本选法后的误差”应分别检验。

在同一批{len(errors):,}组七法共同有效留出测试样本上，以相同的B10目标、β×n条件等权评价：

| 策略 | B10 RMSE | 说明 |
|---|---:|---|
| 报告下原B10地图推荐 | {summaries['report_map']['rmse']:.2f} | 已知真β与n，每格固定一种方法；原图使用全1200组，含本批测试样本 |
| 只用训练部分重建的地图推荐 | {summaries['training_only_map']['rmse']:.2f} | 已知真β与n；选法和测试分开 |
| 网络逐样本选法 | {summaries['network']['rmse']:.2f} | 不输入真β，每组样本可选不同方法 |
| 逐样本事后最优参照 | {summaries['hindsight_reference']['rmse']:.2f} | 使用真误差，实际应用不可获得 |

网络RMSE较原地图低{result['improvement_vs_report_map_pct']:.2f}%，40格中{result['cells_network_lower_rmse']}格的实际测试RMSE更低；较训练重建地图低{result['improvement_vs_training_only_map_pct']:.2f}%（配对95%区间[{ci[0]:.2f}%, {ci[1]:.2f}%]）。原地图用了测试结果，原图对照仅作描述，独立比较应看训练重建地图。

## 选到“最佳方法”有多准

- **逐样本事后最优命中率**：网络{result['network_actual_best_sample_hits']:,}/{len(errors):,}，即{result['network_actual_best_sample_rate']*100:.2f}%；原地图为{result['map_actual_best_sample_rate']*100:.2f}%。这是本批共同有效样本上的严格冠军命中率，不是普遍成功概率。
- **复现地图的条件平均冠军**：把网络预测风险在每格测试样本中取平均再选最小者，仅{result['grid_mean_risk_map_hits']}/40格相同；预测前两名包含原图冠军的为{result['grid_mean_risk_top2_map_hits']}/40格。因此当前不能宣称网络准确重建了原性能地图。
- 网络逐样本选择与所在格子的地图推荐一致率为{result['network_choice_matches_map_sample_rate']*100:.2f}%。地图的冠军是该条件内的平均冠军，不是每个样本的事后冠军，不能直接把这个一致率当作网络选法准确率。

原图一、二名RMSE差距的中位数只有{result['median_map_second_gap_pct']:.2f}%，冠军名称对小误差敏感；这能解释部分排名差异，不能消除网络条件平均风险排名不准确的事实。按网络平均风险选出的每格固定方法，相对原图冠军的RMSE差距中位数为{result['average_risk_choice_map_regret_pct_quantiles'][1]:.2f}%，最大为{result['average_risk_choice_map_regret_pct_quantiles'][-1]:.2f}%。

**本次结论：网络的逐样本选法在这批测试中比照地图选法更有效，但离逐样本真实最优仍有差距；若目标是准确恢复每个β×n条件的最佳方法地图，当前模型尚未达到。** 本比较仍受原训练η=1000、γ=500范围约束。

逐格证据：[map_comparison_cells.csv](结果/B10方法选择-v1/map_comparison_cells.csv)；[汇总JSON](结果/B10方法选择-v1/map_comparison.json)；[比较程序](程序/b10_map_comparison.py)。
'''
    (s.STUDY/'B10方法选择-性能地图对照补充-v1.0.md').write_text(text,encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

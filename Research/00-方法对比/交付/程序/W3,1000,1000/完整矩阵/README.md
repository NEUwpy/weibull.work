# W(3,1000,1000)完整矩阵

n=7、15、30各50组，八方法1200条估计；既有估计复用700条，新增或换版500条。

入口：`run_20261007.py`；配置：`config.json`；母体：`fill_matrix.py`；建表：`build_matrix.mjs`。运行Python入口后，以Node执行建表脚本（需要可用的`@oai/artifact-tool`模块）。所有方法从本批`../依赖快照/python`经runner/registry分派。

原样本及估计来源、SHA见config和manifest。新n30命名空间：`20260907:n30`（传入采样器的seed字符串及repr编码保持固定）；新样本独立保存在数据目录，已有文件不覆盖。

MMLE支撑检查在本调用点传sample_min=x₂，其余方法使用x₁；共享metrics默认语义未改。失败记录保留，不补入其它求解器的解。

图为原形式的MDM梯度—γ曲线，每图50组及一条δ参考线；九张PNG按(n,δ)命名。已有PNG复用原字节。诊断补图使用本批MDM实际trace或其函数AST在求解位置参数前的计算片段，不重算已有参数估计。

LRE继续使用本批历史Bernard实现，未换版。

表头沿用本批历史符号：α为形状、β为尺度、γ为位置。表按n分样本页和结果页，每样本组一行、三档MDM和五个其它方法横向分组，没有标题及备注行。`verify_matrix.py`作本批只读哈希核验；工单全量Excel逐值核验另存于邮箱结果。

续抽样本文件：`数据/samples_n30.csv`，50组，SHA256 `43d71f47eb801b36a3157fc79df5c259b7cc96593fb116c40371aad69f02b05c`；生成代码：`run_20261007.py`调用`fill_matrix.py`中的共享generate_sample。seed编码使用repr(seed)及参数、n和repeat_id。

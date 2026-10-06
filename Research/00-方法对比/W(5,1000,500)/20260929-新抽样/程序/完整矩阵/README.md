# W(5,1000,500)完整矩阵

n=7、15、30各50组，八方法1200条估计；既有估计复用900条，新增或换版300条。

入口：`run_20261007.py`；配置：`config.json`；母体：`fill_matrix.py`；建表：`build_matrix.mjs`。运行Python入口后，以Node执行建表脚本（需要可用的`@oai/artifact-tool`模块）。所有方法从本批`../依赖快照/python`经runner/registry分派。

原样本及估计来源、SHA见config和manifest。三档样本全部复用，原种子命名空间为`2026092903`；本轮未生成新样本。

MMLE支撑检查在本调用点传sample_min=x₂，其余方法使用x₁；共享metrics默认语义未改。失败记录保留，不补入其它求解器的解。

图为原形式的MDM梯度—γ曲线，每图50组及一条δ参考线；九张PNG按(n,δ)命名。已有PNG复用原字节。诊断补图使用本批MDM实际trace或其函数AST在求解位置参数前的计算片段，不重算已有参数估计。

LRE口径变更：Park（2017）Proposed+Plot改回历史Bernard秩回归；前SHA `6daa00d43311ed19bf2d74131220fb51b40e4fd91569f48b981b1beaa8c9c7ae`，后SHA `730e86750f5ac1b31dd1cee9f3a73a8932e501661dfbf1e82c056de44f9a663f`。本批150条LRE已重算，旧实现与旧结果源文件保留；差值记录位于数据/lre_change.json。

表头沿用本批历史符号：α为形状、β为尺度、γ为位置。表按n分样本页和结果页，每样本组一行、三档MDM和五个其它方法横向分组，没有标题及备注行。`verify_matrix.py`作本批只读哈希核验；工单全量Excel逐值核验另存于邮箱结果。

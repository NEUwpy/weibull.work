# 程序流程配置

现行要求以[方法页面开发说明](../../../docs/development/method-pages.md)为准。旧模板“API自动读取带完整代码的JSON”的描述已退役。

schemaVersion=2。配置仅保存方法名称、目的、步骤、公式/符号、输入输出、依据、边界和源码引用；Python正文由接口实时读取。

```json
{
  "schemaVersion": 2,
  "methodId": "mle",
  "methodName": "极大似然估计 (MLE)",
  "description": "沿条件剖面寻找有限候选，比较后返回结果。",
  "steps": [{
    "id": 1,
    "name": "条件形状求解",
    "description": "固定位置，求解受约束的形状方程。",
    "formula": {"expression": "s(\\beta)=0", "symbols": [{"symbol":"\\beta","meaning":"形状参数"}], "explanation":"展示本步实际求解条件。"},
    "inputs": [{"symbol":"\\ln d_i","meaning":"平移观测的对数","code":"logd"}],
    "outputs": [{"symbol":"\\hat\\beta","meaning":"形状候选","code":"beta"}],
    "basis": "标准似然方程与当前工程接受域，详见方法说明。",
    "notes": "同值样本没有有限形状根。",
    "depth": 0,
    "kind": "step",
    "sources": [{"file":"python/methods/conditional_profiles.py","symbol":"_shape","label":"形状求根"}]
  }]
}
```

引用的`symbol`可以是类与嵌套函数路径；可用`after`/`from`/`until`/`through`唯一文本锚点缩小范围。不要手写代码行号；服务端根据现行源码给出原始行号及SHA-256。每步可按计算顺序引用多段含真实可执行语句的源码；辅助函数直接接在本步源码中显示，不增加调用树导航或来源选择按钮。主流程、辅助函数和重要边界均需测试。

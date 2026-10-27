# 程序流程数据模板 (Algorithm Flow Data Template)

本文件定义了算法透明化视图的数据格式，用于展示算法从输入到输出的完整计算过程。

## 文件位置

- 数据文件: `src/data/method_flows/{methodId}.json`
- API路由: `src/app/api/method-flow/[methodId]/route.ts` (已存在，自动读取)

## 数据结构

```json
{
  "methodId": "mle",
  "methodName": "极大似然估计 (MLE)",
  "description": "一句话描述算法的目的",
  "code": [
    "# 算法名称",
    "# 输入: xxx",
    "# 输出: xxx",
    "",
    "import ...",
    "",
    "# ========== 第1步：步骤名称 ==========",
    "# 步骤说明",
    "code_line_1",
    "code_line_2",
    "",
    "# ========== 第2步：步骤名称 ==========",
    ...
  ],
  "steps": [
    {
      "id": 1,
      "name": "步骤名称",
      "description": "步骤描述，说明这一步做什么",
      "codeLines": [12, 13],
      "inputs": [
        {
          "symbol": "变量符号",
          "math": "数学含义 - 使用LaTeX语法",
          "code": "代码含义 - 变量名和类型",
          "value": "当前值 (可选)"
        }
      ],
      "formula": {
        "expression": "公式表达式 - LaTeX语法",
        "symbols": [
          { "symbol": "符号", "meaning": "符号解释" }
        ],
        "explanation": "公式的整体说明"
      },
      "outputs": [
        {
          "symbol": "输出符号",
          "math": "数学含义",
          "code": "代码含义",
          "value": "输出值"
        }
      ],
      "otherVariables": [],
      "isLoop": false,
      "loopCount": "可选，如'~15次迭代'"
    }
  ]
}
```

## 字段说明

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `methodId` | String | 是 | 方法ID，与文件名一致 |
| `methodName` | String | 是 | 方法全名 |
| `description` | String | 是 | 算法目的的简要描述 |
| `code` | String[] | 是 | 完整Python代码，按行分割 |
| `steps` | Array | 是 | 计算步骤数组 |

### 步骤字段

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `id` | Number | 是 | 步骤序号，从1开始 |
| `name` | String | 是 | 步骤名称 |
| `description` | String | 是 | 步骤描述 |
| `codeLines` | Number[] | 是 | 对应的代码行号（从0开始） |
| `inputs` | Array | 是 | 输入变量数组 |
| `formula` | Object | 是 | 公式对象 |
| `outputs` | Array | 是 | 输出变量数组 |
| `otherVariables` | Array | 是 | 其它变量（中间/全局变量） |
| `isLoop` | Boolean | 否 | 是否为循环步骤 |
| `loopCount` | String | 否 | 循环次数说明 |

### 变量字段

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `symbol` | String | 是 | 变量符号 |
| `math` | String | 是 | 数学含义（支持LaTeX） |
| `code` | String | 是 | 代码含义（变量名和类型） |
| `value` | String/Number | 否 | 当前值（用于示例） |

### 公式字段

| 字段 | 类型 | 必填 | 说明 |
|-----|------|------|------|
| `expression` | String | 是 | 公式表达式（LaTeX） |
| `symbols` | Array | 是 | 符号说明数组 |
| `explanation` | String | 是 | 公式整体说明 |

## 步骤组织原则

1. **步骤粒度**: 每个步骤应该是逻辑上的一个计算单元
2. **输入输出明确**: 每个步骤必须明确输入和输出
3. **公式对应**: 每个步骤应该对应一个或一组公式
4. **代码可追溯**: codeLines 应该精确指向实现该步骤的代码行

## 输入输出变量规范

- **输入变量**: 从外部或上一步获得的数据
- **输出变量**: 本步骤计算产生的结果
- **其它变量**: 中间变量或全局变量，按需显示

## 注意事项

1. **LaTeX语法**: 使用 `\\` 转义，如 `\\alpha`, `\\beta`
2. **代码行号**: 从0开始计数
3. **JSON格式**: 确保JSON格式正确，可以使用在线验证器
4. **中英文混排**: 数学符号尽量使用LaTeX，代码部分使用等宽字体

## 示例参考

完整示例请参考: `src/data/method_flows/mle.json`

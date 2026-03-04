/**
 * 图表组件库
 *
 * 组织原则：按方法分类，避免重复
 * - 同一方法内，横纵坐标相同的图表应统一为一个组件
 * - 通用图表放 common/
 * - 方法特有图表放对应方法目录（mdm/, mle/, wmle/）
 *
 * 目录结构：
 * charts/
 * ├── common/         # 通用图表（箱型图、热力图等）
 * ├── mdm/            # MDM方法图表
 * ├── mle/            # MLE方法图表
 * └── wmle/           # WMLE方法图表
 */

// 通用图表组件
export * from './common'

// MDM 方法图表组件
export * from './mdm'

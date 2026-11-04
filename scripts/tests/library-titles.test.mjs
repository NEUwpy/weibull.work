import test from 'node:test'
import assert from 'node:assert/strict'
import { libraryTitlePresentation, libraryPresentedTitle, libraryOriginalLanguage } from '../../src/lib/library-titles.ts'

test('English papers use the existing Chinese title, reveal their original only when expanded and keep canonical fields', () => {
  const paper = { title: 'English paper title', title_en: 'English paper title', noteZh: '已有中文译名', sourceHeading: 'English paper title' }
  const presented = { ...paper, ...libraryTitlePresentation(paper) }
  assert.equal(libraryPresentedTitle(presented), '已有中文译名')
  assert.equal(libraryPresentedTitle(presented, true), 'English paper title')
  assert.equal(presented.title, 'English paper title')
  assert.equal(presented.original_language, 'en')
  assert.equal(libraryTitlePresentation({ ...paper, title: '已核实的公开译名' }).display_title, '已核实的公开译名')
})

test('Chinese originals never switch to their English abstract title and unknown source language is not guessed', () => {
  const paper = { title: '中文论文', title_en: 'An English abstract title', sourceHeading: '中文论文' }
  const presented = { ...paper, ...libraryTitlePresentation(paper) }
  assert.equal(presented.original_language, 'zh')
  assert.equal(libraryPresentedTitle(presented, true), '中文论文')
  const unknown = { title: 'A paper', noteZh: '已有译名' }
  assert.equal(libraryPresentedTitle({ ...unknown, ...libraryTitlePresentation(unknown) }, true), '已有译名')
  assert.equal(libraryOriginalLanguage('ワイブル分布の形状母数推定の新方法'), 'other')
  assert.equal(libraryOriginalLanguage('طراحى یک شبکه عصبی'), 'other')
})

test('cover headings and fused OCR headings give way to real note titles, and formula markup survives translation', () => {
  assert.equal(libraryTitlePresentation({ title: '博士学位论文', noteZh: '论文的实际题名', sourceHeading: '博士学位论文' }).display_title, '论文的实际题名')
  assert.equal(libraryTitlePresentation({ title: '中文题目MAXIMUM LIKELIHOOD ESTIMATION PARAMETER METHOD', noteZh: '中文题目' }).display_title, '中文题目')
  const math = libraryTitlePresentation({ title: 'Estimation of $R = P ( Y < X )$', noteZh: '三参数威布尔分布下 R=P(Y<X) 的估计', sourceHeading: 'Estimation of $R = P ( Y < X )$' })
  assert.equal(math.display_title, '三参数威布尔分布下 $R = P ( Y < X )$ 的估计')
  const native = libraryTitlePresentation({ title: '威布尔分布下小样本 $P - S - N$ 曲线拟合方法', noteZh: '威布尔分布下小样本P-S-N曲线拟合方法', sourceHeading: '威布尔分布下小样本 $P - S - N$ 曲线拟合方法' })
  assert.match(native.display_title, /\$P - S - N\$/)
})

test('the sole missing Chinese title has an explicit translation; other missing translations retain the source honestly', () => {
  assert.equal(libraryTitlePresentation({ title: 'Bias and Standard Deviation due to Weibull Parameter Estimation for Small Data Sets', sourceTitle: 'R. Ross' }).display_title,
    '小数据集威布尔参数估计的偏差与标准差')
  assert.equal(libraryTitlePresentation({ title: 'A newly selected paper' }).display_title, 'A newly selected paper')
})

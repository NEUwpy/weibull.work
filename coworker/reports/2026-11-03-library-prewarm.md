# 图书馆自动预热验收（2026-11-03）

新增书单后原请求在本地检索阶段等待约105秒。此前启动预热只执行一次，运行中更新留给首次搜索承担。本次运行机制集中在[文献库README](../../docs/library/README.md#网站正文检索与ai问答)。保留原检索评分、书单及100/400源稿。

## 验证

- `node --disable-warning=MODULE_TYPELESS_PACKAGE_JSON --experimental-strip-types --test scripts/tests/library-prewarm.test.mjs scripts/tests/library-fulltext-search.test.mjs scripts/tests/library-rag.test.mjs scripts/tests/library-auth.test.mjs scripts/tests/library-integration.test.mjs`：40项通过。覆盖书单增删、单稿更新、未变化不读正文、跨模块单定时器、并发复用、解析让出执行时间、更新中再次保存和失败后重试，以及原检索、问答、登录边界。
- 真实Node定时器、临时source选单：初始选1篇，增加第2篇后不发搜索；10091ms后缓存自动包含2篇，总解析2稿。随后搜索新段落成功，正文读取0次。临时资料已清理，正式选单未改。
- `npm run build`：退出码0，含类型检查及32个静态页。构建仍有既有Browserslist数据过期和edge编译worker退出提示，最终成功。
- 本机启动器重启3000前端，后端8001保持运行。启动日志先记录`Index ready { documents: 318, papers: 251, passages: 61635, elapsedMs: 17749 }`，再记录`Ready in 27.9s`。
- 启动后HTTP搜索“极大似然估计”均返回415处命中：首次3898ms（含开发路由编译），后续76ms、67ms。本机观测不代表跨机器性能保证。
- 原句“都谁研究极大似然方法”的真实AI问答完成，含开发路由准备约7.5秒开始输出、15.7秒完成，无接口错误。

运行日志仍在`D:/weibull-data/logs/local-launcher/`。变更只在本机生效，未部署NAS/公网；Docker standalone启动入口仍按文献库README的发布限制处理。

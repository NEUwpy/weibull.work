# 页头字体资源

仅供公共页头的六组中英文标题使用，不应用到正文或导航。

| 文件 | 原字体 | 字重 |
|---|---|---|
| `header-linux-libertine-g-bold.woff2` | Linux Libertine G Bold（字体内部名 `LinuxLibertineGB`） | 700 |
| `header-yanzhenqing.woff2` | 方正颜真卿楷书 简繁（字体内部名 `FZYanZhenQingKaiShuJF`） | 原字体字形，对应页头 500 |

资源从本机现有字体提取标题字符并转换为 WOFF2，未包含整套字库。标题内容以 `src/app/layout.tsx` 为准；修改标题时须检查字形覆盖，新增字符后重新生成子集。仅调整字号无需重新生成。

生成工具为 FontTools 的 `pyftsubset`，使用 `--text` 传入现行标题字符，指定 `--flavor=woff2 --no-recalc-timestamp --output-file=<目标文件>`。字体原件保留在本机字体目录，不随项目复制。

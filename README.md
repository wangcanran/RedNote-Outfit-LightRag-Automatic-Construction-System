# RedNote Outfit — 爬取 · 标注 · LightRAG 知识图谱构建

本仓库从主项目抽取**一条链**相关代码：**数据爬取 → 穿搭标注 → LightRAG 文档化入库 → 输出知识图谱**。

## 目录与脚本

| 环节 | 说明 |
|------|------|
| 爬取 | `crawlers/xiaohongshu_clothing_crawler.py`，输出默认在 `crawlers/clothing_data/` |
| 标注 | `tag_annotation.py`（视觉 + 文本标签 + `outfit_organizer` 拆套） |
| 建图 | `kg_builder.py`，读取 `*_annotated.json`，写入 `kg_storage/` |

详细说明见仓库内 `CRAWLER_USAGE.md`、`KNOWLEDGE_GRAPH_GUIDE.md`。

## 环境

1. 复制环境变量模板：`copy .env.example .env`（按注释填写 API）。
2. 安装依赖（**在仓库根目录**执行，以便安装本地 `LightRAG`）：

```powershell
pip install -r requirements.txt
```

## 典型命令（在项目根）

```powershell
# 1) 爬取（需浏览器环境，见 CRAWLER_USAGE.md）
python crawlers/xiaohongshu_clothing_crawler.py

# 2) 标注（输入爬取 JSON，输出 *_annotated.json，参数以你本地为准）
python tag_annotation.py crawlers/clothing_data/clothing_posts_xxx.json

# 3) 建图
python kg_builder.py crawlers/clothing_data/clothing_posts_xxx_annotated.json
```

## 推送到 GitHub

```powershell
cd <本仓库根目录>
git init
git add .
git commit -m "Initial import: crawl, annotate, LightRAG KG pipeline"
git branch -M main
git remote add origin git@github.com:wangcanran/RedNote-Outfit-LightRag-Automatic-Construction-System.git
git push -u origin main
```

> 若远程已有 README/commit，请先 `git pull origin main --allow-unrelated-histories` 再合并推送。

## 许可

内置 `LightRAG/` 来自 HKU LightRAG 项目，以该子目录内 LICENSE 为准；其余脚本以你主仓库约定为准。

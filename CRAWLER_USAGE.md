# 小红书服装标签爬虫使用指南

## 功能概述

这个爬虫系统用于从小红书爬取服装相关帖子，提取并分类标签，为构建服装知识图谱提供数据支持。

## 核心功能

### 1. 数据爬取 (`xiaohongshu_clothing_crawler.py`)

**爬取维度：**
- 季节：春季穿搭、夏季穿搭、秋季穿搭、冬季穿搭
- 风格：甜美风、休闲风、性感风、韩系、日系、欧美风等
- 天气：下雨天穿搭、晴天穿搭、降温穿搭等
- 温度：10度穿搭、15度穿搭、20度穿搭等
- 品类：连衣裙、T恤、牛仔裤、卫衣等

**采集数据：**
- 帖子ID、标题、描述
- 标签列表（重要！）
- 作者信息
- 互动数据（点赞、收藏、评论数）
- 帖子URL、封面图

### 2. 标签提取 (`tag_extractor.py`)

**标签分类：**
- **风格标签**：甜美、性感、休闲、韩系、日系、复古等
- **季节标签**：春季、夏季、秋季、冬季
- **天气标签**：晴天、雨天、降温、回暖等
- **温度标签**：5度、10度、15度、20度等
- **颜色标签**：黑色、白色、红色、莫兰迪色等
- **材质标签**：棉、丝、麻、羊毛、牛仔等
- **品类标签**：T恤、连衣裙、牛仔裤、卫衣等
- **场景标签**：通勤、约会、旅行、运动等
- **身材标签**：显瘦、显高、小个子、微胖等
- **价格标签**：平价、轻奢、高性价比等

## 使用步骤

### 步骤1：安装依赖

```bash
pip install DrissionPage
```

### 步骤2：运行爬虫

```bash
cd crawlers
python xiaohongshu_clothing_crawler.py
```

**交互选项：**
1. 选择爬取模式（预定义关键词 / 自定义关键词）
2. 设置每个关键词的滚动次数（默认10次）

**输出文件：**
- `clothing_data/clothing_posts_YYYYMMDD_HHMMSS.csv` - CSV格式数据
- `clothing_data/clothing_posts_YYYYMMDD_HHMMSS.json` - JSON格式数据
- `clothing_data/tags_summary.json` - 标签统计摘要

### 步骤3：提取和分析标签

```bash
python tag_extractor.py clothing_data/clothing_posts_20260414_120000.json
```

**输出文件：**
- `clothing_data/clothing_posts_20260414_120000_analysis.json`

**包含内容：**
- 标签分类统计（每个类别的标签及出现次数）
- 知识图谱数据（节点和关系）

## 数据格式

### 爬取数据格式 (JSON)

```json
{
  "post_id": "64a1b2c3d4e5f6",
  "title": "春季甜美穿搭分享",
  "desc": "15度天气穿这套超合适...",
  "tags": ["春季穿搭", "甜美风", "连衣裙"],
  "search_keyword": "春季穿搭",
  "author_nickname": "小红薯123",
  "liked_count": 1520,
  "collected_count": 380,
  "comment_count": 45,
  "post_url": "https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6",
  "crawl_time": "2026-04-14T12:00:00"
}
```

### 分析结果格式 (JSON)

```json
{
  "analysis": {
    "total_posts": 500,
    "categories": {
      "style": {
        "total_unique_tags": 15,
        "tags": [
          {"tag": "甜美", "count": 120},
          {"tag": "休闲", "count": 95}
        ]
      },
      "season": {...},
      "temperature": {...}
    }
  },
  "knowledge_graph": {
    "nodes": [
      {
        "id": "style:甜美",
        "type": "style",
        "label": "甜美",
        "count": 120,
        "post_count": 115
      }
    ],
    "relationships": [
      {
        "source": "style:甜美",
        "target": "season:春季",
        "weight": 45
      }
    ]
  }
}
```

## 与知识图谱集成

### 下一步：使用 LightRAG 构建知识图谱

1. **准备数据**：将爬取的帖子数据转换为文本格式
2. **导入 LightRAG**：使用 LightRAG 构建知识图谱
3. **查询图谱**：查询品类关系、风格搭配、季节趋势等
4. **选品决策**：基于图谱数据为选品 Agent 提供决策支持

### 与现有 Agent 集成

```python
# 示例：将标签数据用于选品决策
from crawlers.tag_extractor import ClothingTagExtractor

extractor = ClothingTagExtractor()
analysis = extractor.analyze_posts(posts)

# 获取当前热门风格
hot_styles = analysis['categories']['style']['tags'][:5]

# 传递给 CategoryAgent 进行决策
category_agent.analyze({
    'trending_styles': hot_styles,
    'season': '春季',
    'temperature_range': '15-20度'
})
```

## 注意事项

1. **反爬虫**：
   - 每个关键词之间有5秒延迟
   - 建议分批爬取，避免一次爬取过多
   - 可能需要登录小红书账号

2. **数据质量**：
   - 标签提取基于预定义词典，可能遗漏新兴标签
   - 建议定期更新 `TAG_CATEGORIES` 词典
   - 可以结合 LLM 进行更智能的标签提取

3. **浏览器要求**：
   - DrissionPage 需要 Chrome/Chromium 浏览器
   - 首次运行会自动下载 ChromeDriver

## 扩展功能

### 自定义标签类别

编辑 `tag_extractor.py` 中的 `TAG_CATEGORIES` 字典：

```python
TAG_CATEGORIES = {
    'style': ['甜美', '性感', ...],
    'custom_category': ['自定义标签1', '自定义标签2']
}
```

### 自定义搜索关键词

编辑 `xiaohongshu_clothing_crawler.py` 中的 `SEARCH_KEYWORDS` 列表：

```python
SEARCH_KEYWORDS = [
    "你的关键词1",
    "你的关键词2",
    ...
]
```

## 故障排查

**问题1：无法启动浏览器**
- 确保已安装 Chrome 浏览器
- 检查 DrissionPage 版本：`pip install --upgrade DrissionPage`

**问题2：爬取不到数据**
- 检查网络连接
- 尝试手动访问小红书确认可访问
- 可能需要登录账号

**问题3：标签提取不准确**
- 更新 `TAG_CATEGORIES` 词典
- 考虑使用 Claude API 进行智能标签提取

## 性能优化

- **并发爬取**：可以修改代码支持多关键词并发
- **增量更新**：记录已爬取的帖子ID，避免重复爬取
- **数据去重**：基于 post_id 去重

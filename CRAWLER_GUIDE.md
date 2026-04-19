"""
小红书爬虫使用指南

## 功能说明

XiaohongshuCrawler 是一个用于采集小红书服装相关内容的爬虫，主要功能包括：

1. **搜索采集** - 根据关键词搜索并采集帖子
2. **数据解析** - 提取帖子的基础信息和服装属性
3. **属性识别** - 自动识别品类、风格、颜色、季节、价格段
4. **数据存储** - 保存采集的数据为 JSON 格式
5. **统计分析** - 生成采集数据的统计报告

## 采集的数据字段

每条帖子包含以下信息：

- post_id: 帖子ID
- title: 帖子标题
- content: 帖子内容
- author_id: 作者ID
- author_name: 作者名称
- publish_time: 发布时间
- likes: 点赞数
- collects: 收藏数
- comments: 评论数
- shares: 分享数
- images: 图片URL列表
- tags: 话题标签
- category: 服装品类（连衣裙、T恤、牛仔裤等）
- style: 风格标签（甜美、性感、休闲等）
- color: 颜色标签（黑、白、红等）
- season: 季节标签（春、夏、秋、冬）
- price_range: 价格段（平价、中端、高端）
- engagement_rate: 互动率
- crawl_time: 采集时间

## 使用方法

### 基础使用

```python
from crawlers.xiaohongshu_crawler import XiaohongshuCrawler

# 初始化爬虫
crawler = XiaohongshuCrawler()

# 定义搜索关键词
keywords = ['连衣裙', '甜美风格', '春季穿搭']

# 采集数据
posts = crawler.search_posts(keywords, limit=50)

# 保存数据
crawler.save_posts(posts, 'posts.json')

# 获取统计信息
stats = crawler.get_statistics(posts)
print(stats)
```

### 加载已保存的数据

```python
# 加载数据
posts = crawler.load_posts('posts.json')

# 获取统计
stats = crawler.get_statistics(posts)
```

## 重要说明

### 反爬虫处理

小红书有反爬虫机制，实际使用时需要：

1. **使用代理IP** - 避免IP被封禁
2. **控制请求频率** - 添加随机延迟
3. **模拟浏览器** - 使用真实的 User-Agent
4. **处理验证码** - 可能需要手动验证或使用验证码识别服务
5. **使用 Selenium/Playwright** - 模拟真实浏览器行为

### 法律合规

- 遵守小红书的服务条款
- 不采集个人隐私信息
- 不用于商业竞争目的
- 仅用于学习和研究

### 属性识别准确性

当前的属性识别（品类、风格、颜色等）基于关键词匹配，准确性有限。
后续可以通过以下方式改进：

1. 集成 NLP 模型进行更精准的实体识别
2. 使用 LightRAG 构建知识图谱
3. 结合图像识别技术分析图片中的服装属性

## 下一步

1. 完善反爬虫处理
2. 集成 LightRAG 进行知识图谱构建
3. 实现更精准的属性识别
4. 构建选品决策引擎
"""

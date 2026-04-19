# 服装知识图谱系统完整指南

## 系统架构

```
小红书爬虫 → 数据采集 → 标签提取 → 知识图谱构建 → 选品决策 → 业务智能体
```

### 核心组件

1. **数据采集层** (`crawlers/`)
   - `xiaohongshu_clothing_crawler.py` - 小红书爬虫
   - `tag_extractor.py` - 标签提取和分类

2. **知识图谱层** (`kg_builder.py`)
   - 基于 LightRAG 构建知识图谱
   - 实体和关系提取
   - 多模式查询（local/global/hybrid）

3. **决策层** (`agents/`)
   - `product_selection_agent.py` - 选品决策 Agent
   - `pricing_agent.py` - 定价策略 Agent
   - `inventory_agent.py` - 库存优化 Agent
   - `category_agent.py` - 品类管理 Agent

4. **API 层** (`api.py`)
   - RESTful API 接口
   - FastAPI 框架

## 完整使用流程

### 第一步：数据采集

```bash
# 1. 运行小红书爬虫
cd crawlers
python xiaohongshu_clothing_crawler.py

# 选择模式：
# 1 - 使用预定义关键词（推荐）
# 2 - 自定义关键词

# 输出文件：
# - clothing_data/clothing_posts_YYYYMMDD_HHMMSS.json
# - clothing_data/clothing_posts_YYYYMMDD_HHMMSS.csv
# - clothing_data/tags_summary.json
```

**预定义关键词覆盖：**
- 季节：春季穿搭、夏季穿搭、秋季穿搭、冬季穿搭
- 风格：甜美风、休闲风、韩系、日系、欧美风等
- 天气：下雨天穿搭、晴天穿搭、降温穿搭
- 温度：10度穿搭、15度穿搭、20度穿搭等
- 品类：连衣裙、T恤、牛仔裤、卫衣等

### 第二步：标签提取和分析

```bash
# 提取和分类标签
python tag_extractor.py clothing_data/clothing_posts_20260414_120000.json

# 输出文件：
# - clothing_data/clothing_posts_20260414_120000_analysis.json
```

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

### 第三步：构建知识图谱

```bash
# 从 JSON 数据构建知识图谱
python kg_builder.py clothing_data/clothing_posts_20260414_120000.json

# 可选：指定存储目录
python kg_builder.py clothing_data/clothing_posts_20260414_120000.json kg_storage_custom

# 知识图谱存储在：kg_storage/
```

**知识图谱包含：**
- **节点类型**：品类、风格、颜色、材质、季节、温度、场景等
- **关系类型**：
  - 品类 → 风格（连衣裙 适合 甜美风）
  - 风格 → 季节（甜美风 适合 春夏）
  - 品类 → 温度（T恤 适合 25-30度）
  - 颜色 → 搭配（黑色 搭配 白色）
  - 品类 → 场景（西装 适合 通勤）

### 第四步：使用选品 Agent

#### 方式1：Python 代码调用

```python
import asyncio
from agents.product_selection_agent import ProductSelectionAgent

async def main():
    agent = ProductSelectionAgent()
    
    try:
        # 定义选品条件
        criteria = {
            'season': '春季',
            'temperature_range': '15-20度',
            'target_style': '甜美',
            'occasion': '日常通勤',
            'price_range': '平价',
            'target_audience': '年轻女性'
        }
        
        # 获取选品建议
        result = await agent.analyze_async(criteria)
        
        # 查看推荐
        recommendation = result['recommendation']
        print("推荐品类:", recommendation['recommended_categories'])
        print("风格方向:", recommendation['style_direction'])
        print("定价策略:", recommendation['pricing_strategy'])
        
    finally:
        await agent.finalize()

asyncio.run(main())
```

#### 方式2：API 调用

```bash
# 启动 API 服务器
python main.py

# API 运行在 http://localhost:8000
# 文档地址：http://localhost:8000/docs
```

**API 端点：**

1. **选品分析**
```bash
curl -X POST "http://localhost:8000/selection/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "season": "春季",
    "target_style": "甜美",
    "temperature_range": "15-20度",
    "occasion": "日常通勤",
    "price_range": "平价",
    "target_audience": "年轻女性"
  }'
```

2. **快速选品**
```bash
curl "http://localhost:8000/selection/quick/春季?budget=medium"
```

### 第五步：集成到现有业务流程

```python
# 示例：将选品建议用于库存和定价决策

from agents.product_selection_agent import get_selection_recommendation_async
from agents.inventory_agent import InventoryAgent
from agents.pricing_agent import PricingAgent

async def optimize_business():
    # 1. 获取选品建议
    criteria = {
        'season': '春季',
        'target_style': '甜美',
        'price_range': '平价'
    }
    
    selection = await get_selection_recommendation_async(criteria)
    recommended_categories = selection['recommendation']['recommended_categories']
    
    # 2. 根据选品建议调整库存
    inventory_agent = InventoryAgent()
    for category in recommended_categories:
        if category['priority'] == 'high':
            # 增加高优先级品类的库存
            inventory_data = {
                'product_id': category['category'],
                'product_name': category['category'],
                'stock': 100,
                'turnover_rate': 3.0,
                'dead_stock_days': 10,
                'trend': 'rising',
                'reorder_point': 50
            }
            inventory_strategy = inventory_agent.analyze(inventory_data)
            print(f"库存建议: {inventory_strategy}")
    
    # 3. 根据选品建议调整定价
    pricing_agent = PricingAgent()
    pricing_strategy = selection['recommendation']['pricing_strategy']
    print(f"定价策略: {pricing_strategy}")
```

## 知识图谱查询示例

### 直接查询知识图谱

```python
import asyncio
from kg_builder import ClothingKnowledgeGraph

async def query_examples():
    kg = ClothingKnowledgeGraph()
    await kg.initialize()
    
    try:
        # 1. 查询热门品类
        result = await kg.get_trending_categories()
        print("热门品类:", result['answer'])
        
        # 2. 查询特定风格
        result = await kg.get_style_recommendations("甜美")
        print("甜美风格建议:", result['answer'])
        
        # 3. 查询季节趋势
        result = await kg.get_seasonal_trends("春季")
        print("春季趋势:", result['answer'])
        
        # 4. 查询温度适配
        result = await kg.analyze_temperature_range("15-20度")
        print("温度适配:", result['answer'])
        
        # 5. 自定义查询
        result = await kg.query(
            "推荐适合小个子女生的春季穿搭",
            mode="hybrid"
        )
        print("自定义查询:", result['answer'])
        
    finally:
        await kg.finalize()

asyncio.run(query_examples())
```

### 查询模式说明

- **local**: 基于特定实体的局部查询（适合精确查询）
- **global**: 基于全局社区的宏观查询（适合趋势分析）
- **hybrid**: 结合 local 和 global（推荐）
- **naive**: 直接向量搜索（不使用图结构）
- **mix**: 整合知识图谱和向量检索（最全面）

## 数据流示例

### 完整的选品决策流程

```
1. 小红书爬虫采集数据
   ↓
   输出：500条帖子，包含标题、描述、标签、互动数据
   
2. 标签提取器分类
   ↓
   输出：10个类别，200+个唯一标签
   
3. 知识图谱构建
   ↓
   输出：实体节点（品类、风格、颜色等）+ 关系边（搭配、适合等）
   
4. 选品 Agent 查询
   ↓
   输入：季节=春季，风格=甜美，温度=15-20度
   ↓
   知识图谱返回：
   - 春季热门品类：连衣裙、针织衫、风衣
   - 甜美风格特征：粉色、蕾丝、碎花
   - 15-20度适配：薄外套、长袖T恤
   ↓
   Agent 综合分析
   ↓
   输出：
   {
     "recommended_categories": [
       {
         "category": "连衣裙",
         "priority": "high",
         "colors": ["粉色", "白色", "浅蓝"],
         "materials": ["雪纺", "棉"],
         "price_suggestion": "99-299元",
         "expected_demand": "high"
       }
     ],
     "confidence_score": 0.87
   }
   
5. 业务决策
   ↓
   - 库存 Agent：增加连衣裙库存30%
   - 定价 Agent：定价区间 99-299元
   - 品类 Agent：推广春季甜美系列
```

## 配置说明

### 环境变量 (.env)

```bash
# Claude API 配置
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_BASE_URL=https://api.anthropic.com  # 可选，国内可用代理

# 模型配置
MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=4096
TEMPERATURE=0.7

# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# 数据库配置
DATABASE_URL=sqlite:///./ecommerce.db
```

### 知识图谱配置

```python
# kg_builder.py 中可配置：

# LLM 模型
llm_model_name = "claude-3-5-sonnet-20241022"

# Embedding 模型
embedding_model = "text-embedding-3-small"

# 批处理大小
batch_size = 10  # 每批处理的帖子数

# 存储目录
working_dir = "kg_storage"
```

## 性能优化

### 1. 爬虫优化
- 并发爬取多个关键词
- 增量更新（避免重复爬取）
- 数据去重（基于 post_id）

### 2. 知识图谱优化
- 批量插入文档（batch_size=10-20）
- 使用向量数据库（Milvus/Qdrant）替代默认存储
- 定期清理过期数据

### 3. 查询优化
- 缓存常见查询结果
- 使用 hybrid 或 mix 模式平衡准确性和速度
- 调整 top_k 参数（默认20，可增加到50）

## 故障排查

### 问题1：知识图谱初始化失败
```
错误：AttributeError: __aenter__
解决：确保调用了 await kg.initialize()
```

### 问题2：查询结果不准确
```
原因：数据量太少或标签提取不准确
解决：
1. 增加爬取数据量（至少500条帖子）
2. 更新 tag_extractor.py 中的 TAG_CATEGORIES
3. 使用更强的 LLM 模型
```

### 问题3：API 响应慢
```
原因：知识图谱查询耗时
解决：
1. 使用缓存
2. 减少 top_k 参数
3. 使用 local 模式替代 hybrid
```

## 扩展功能

### 1. 添加新的标签类别

编辑 `crawlers/tag_extractor.py`:

```python
TAG_CATEGORIES = {
    'style': [...],
    'custom_category': ['标签1', '标签2', ...]
}
```

### 2. 自定义知识图谱查询

```python
# 在 kg_builder.py 中添加新方法
async def custom_query(self, question: str) -> Dict:
    return await self.query(question, mode="hybrid", top_k=30)
```

### 3. 集成其他数据源

```python
# 除了小红书，还可以集成：
# - 淘宝/天猫商品数据
# - 抖音/快手短视频数据
# - 微博时尚博主内容
# - 电商平台销售数据
```

## 最佳实践

1. **数据采集**：每周更新一次，保持数据新鲜度
2. **标签维护**：每月审查和更新标签词典
3. **知识图谱**：季节变化时重建图谱
4. **选品决策**：结合历史销售数据验证建议
5. **持续优化**：根据实际销售结果调整模型

## 下一步计划

- [ ] 添加图像识别（识别服装款式和颜色）
- [ ] 集成销售数据进行效果验证
- [ ] 开发可视化界面展示知识图谱
- [ ] 支持多平台数据源（淘宝、抖音等）
- [ ] 添加用户画像分析

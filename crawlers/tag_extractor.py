"""
服装标签提取和分类工具
从小红书爬取的数据中提取并分类标签：风格、季节、天气、温度、颜色、材质、品类等
支持分层识别：关键词匹配 + 图像识别 + 大模型识别（热门帖子）
"""
import json
import re
import sys
from typing import Dict, List, Set
from collections import defaultdict
from pathlib import Path

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from llm_client import get_llm_client, get_model_name


class ClothingTagExtractor:
    """服装标签提取器"""

    # 预定义标签分类词典
    TAG_CATEGORIES = {
        # 风格标签
        'style': [
            '甜美', '性感', '休闲', '正式', '通勤', '运动', '街头',
            '韩系', '日系', '欧美', '复古', '简约', '优雅', '可爱',
            '帅气', '淑女', '文艺', '森系', '学院', '朋克', '嘻哈',
            '波西米亚', '极简', '轻奢', '法式', '港风', '辣妹'
        ],

        # 季节标签
        'season': [
            '春季', '夏季', '秋季', '冬季', '春天', '夏天', '秋天', '冬天',
            '春装', '夏装', '秋装', '冬装', '早春', '初秋', '早秋', '深秋',
            '换季', '四季'
        ],

        # 天气标签
        'weather': [
            '晴天', '阴天', '雨天', '下雨', '雪天', '下雪',
            '降温', '回暖', '升温', '变天', '多云', '大风'
        ],

        # 温度标签（通过正则匹配）
        'temperature': [
            '5度', '10度', '15度', '20度', '25度', '30度', '35度',
            '零下', '低温', '高温', '恒温'
        ],

        # 颜色标签
        'color': [
            '黑色', '白色', '红色', '蓝色', '绿色', '黄色', '粉色', '紫色',
            '灰色', '棕色', '橙色', '米色', '卡其', '藏青', '深蓝', '浅蓝',
            '深灰', '浅灰', '裸色', '驼色', '军绿', '墨绿', '酒红', '枣红',
            '黑白', '彩色', '纯色', '撞色', '莫兰迪', '大地色'
        ],

        # 材质标签
        'material': [
            '棉', '纯棉', '丝', '真丝', '麻', '亚麻', '羊毛', '羊绒',
            '皮革', '牛仔', '雪纺', '针织', '毛呢', '绒面', '丝绒',
            '涤纶', '尼龙', '莱卡', '氨纶', '天鹅绒', '灯芯绒'
        ],

        # 品类标签
        'category': [
            'T恤', '衬衫', '卫衣', '毛衣', '针织衫', '外套', '大衣', '风衣',
            '羽绒服', '棉服', '西装', '夹克', '牛仔外套', '皮衣',
            '连衣裙', '半身裙', '长裙', '短裙', 'A字裙', '百褶裙',
            '裤子', '牛仔裤', '休闲裤', '西裤', '阔腿裤', '直筒裤', '喇叭裤',
            '短裤', '打底裤', '运动裤', '背心', '吊带', '马甲'
        ],

        # 场景标签
        'occasion': [
            '上班', '通勤', '约会', '聚会', '旅行', '度假', '运动', '健身',
            '逛街', '日常', '居家', '派对', '婚礼', '面试', '开学', '毕业',
            '拍照', '出游', '上学', '职场'
        ],

        # 身材标签
        'body_type': [
            '显瘦', '显高', '遮肉', '小个子', '高个子', '微胖', '梨形身材',
            '苹果型', 'H型', 'A型', 'X型', '沙漏型', '宽肩', '窄肩',
            '长腿', '短腿', '粗腿', '细腿'
        ],

        # 价格标签
        'price': [
            '平价', '高性价比', '性价比', '便宜', '实惠', '学生党',
            '轻奢', '高端', '奢侈', '大牌', '小众', '国货'
        ]
    }

    def __init__(self):
        """初始化提取器"""
        # 构建反向索引：标签 -> 类别
        self.tag_to_category = {}
        for category, tags in self.TAG_CATEGORIES.items():
            for tag in tags:
                self.tag_to_category[tag] = category

        # 初始化 LLM 客户端（用于热门帖子的大模型识别）
        self.claude_client = get_llm_client()
        self.model_name = get_model_name()

    def extract_from_text(self, text: str) -> Dict[str, List[str]]:
        """
        从文本中提取分类标签

        Args:
            text: 输入文本（标题、描述等）

        Returns:
            分类后的标签字典
        """
        categorized_tags = defaultdict(list)

        # 遍历所有预定义标签
        for category, tags in self.TAG_CATEGORIES.items():
            for tag in tags:
                if tag in text:
                    categorized_tags[category].append(tag)

        # 特殊处理：温度标签（正则匹配）
        temp_pattern = r'(\d+)度'
        temp_matches = re.findall(temp_pattern, text)
        for temp in temp_matches:
            categorized_tags['temperature'].append(f'{temp}度')

        # 去重
        for category in categorized_tags:
            categorized_tags[category] = list(set(categorized_tags[category]))

        return dict(categorized_tags)

    def extract_from_post(self, post: Dict, use_llm: bool = False) -> Dict[str, List[str]]:
        """
        从帖子数据中提取分类标签

        Args:
            post: 帖子数据字典
            use_llm: 是否使用大模型识别（用于热门帖子）

        Returns:
            分类后的标签字典
        """
        # 合并标题、描述、标签进行提取
        text = ' '.join([
            post.get('title', ''),
            post.get('desc', ''),
            ' '.join(post.get('tags', []))
        ])

        # 第一层：关键词匹配
        categorized = self.extract_from_text(text)
        print(f"    [关键词匹配] 提取 {sum(len(v) for v in categorized.values())} 个标签")

        # 第二层：图像识别
        if 'image_analysis' in post:
            visual_tags = self._extract_visual_tags(post['image_analysis'])
            for category, tags in visual_tags.items():
                if category not in categorized:
                    categorized[category] = []
                categorized[category].extend(tags)
                categorized[category] = list(set(categorized[category]))  # 去重
            print(f"    [图像识别] 新增 {sum(len(v) for v in visual_tags.values())} 个标签")

        # 第三层：大模型识别（tag_annotation 传 use_llm=True 时每帖都会走这里）
        if use_llm:
            print(
                f"    [大模型识别] 调用 LLM（{self.model_name}）补全标签...",
                flush=True,
            )
            llm_tags = self._extract_tags_with_llm(text, categorized)
            for category, tags in llm_tags.items():
                if category not in categorized:
                    categorized[category] = []
                categorized[category].extend(tags)
                categorized[category] = list(set(categorized[category]))  # 去重
            print(f"    [大模型识别] 新增 {sum(len(v) for v in llm_tags.values())} 个标签")

        return categorized

    def _extract_visual_tags(self, image_analysis: Dict) -> Dict[str, List[str]]:
        """
        从图像分析结果中提取标签

        Args:
            image_analysis: 图像分析结果

        Returns:
            分类后的视觉标签
        """
        visual_tags = defaultdict(list)

        # 品类标签
        if image_analysis.get('categories'):
            visual_tags['category'].extend(image_analysis['categories'])

        # 风格标签
        if image_analysis.get('overall_style'):
            visual_tags['style'].extend(image_analysis['overall_style'])

        # 颜色标签
        if image_analysis.get('color_scheme'):
            color_scheme = image_analysis['color_scheme']
            if color_scheme.get('primary'):
                visual_tags['color'].append(color_scheme['primary'])
            if color_scheme.get('secondary'):
                visual_tags['color'].extend(color_scheme['secondary'])

        # 场景标签
        if image_analysis.get('occasions'):
            visual_tags['occasion'].extend(image_analysis['occasions'])

        # 季节标签
        if image_analysis.get('seasons'):
            visual_tags['season'].extend(image_analysis['seasons'])

        # 身材标签
        if image_analysis.get('body_types'):
            visual_tags['body_type'].extend(image_analysis['body_types'])

        # 从单品详情中提取材质和款式
        if image_analysis.get('items'):
            for item in image_analysis['items']:
                # 材质
                if item.get('material'):
                    visual_tags['material'].append(item['material'])

                # 款式（从 style 字段）
                if item.get('style'):
                    visual_tags['category'].append(item['style'])

                # 颜色
                if item.get('colors'):
                    visual_tags['color'].extend(item['colors'])

        # 从预定义标签中提取
        if image_analysis.get('tags'):
            for tag in image_analysis['tags']:
                # 查找标签所属的类别
                for category, category_tags in self.TAG_CATEGORIES.items():
                    if tag in category_tags:
                        visual_tags[category].append(tag)
                        break

        # 去重
        for category in visual_tags:
            visual_tags[category] = list(set(visual_tags[category]))

        return dict(visual_tags)

    def _extract_tags_with_llm(self, text: str, existing_tags: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        使用大模型识别遗漏的标签（仅用于热门帖子）

        Args:
            text: 输入文本
            existing_tags: 已有的标签（用于避免重复）

        Returns:
            新识别的标签
        """
        try:
            # 构建已有标签列表
            existing_tag_list = []
            for tags in existing_tags.values():
                existing_tag_list.extend(tags)

            # 构建提示
            prompt = f"""从以下服装穿搭文本中识别遗漏的标签。

已有标签: {', '.join(existing_tag_list)}

文本内容:
{text}

请识别以下类别中遗漏的标签（不要重复已有标签）：

1. 风格 (style): 甜美、性感、休闲、正式、通勤、运动、街头、韩系、日系、欧美、复古、简约、优雅、可爱、帅气、淑女、文艺、森系、学院、朋克、嘻哈、波西米亚、极简、轻奢、法式、港风、辣妹

2. 季节 (season): 春季、夏季、秋季、冬季、春天、夏天、秋天、冬天、春装、夏装、秋装、冬装、早春、初秋、早秋、深秋、换季、四季

3. 天气 (weather): 晴天、阴天、雨天、下雨、雪天、下雪、降温、回暖、升温、变天、多云、大风

4. 温度 (temperature): 5度、10度、15度、20度、25度、30度、35度、零下、低温、高温、恒温

5. 颜色 (color): 黑色、白色、红色、蓝色、绿色、黄色、粉色、紫色、灰色、棕色、橙色、米色、卡其、藏青、深蓝、浅蓝、深灰、浅灰、裸色、驼色、军绿、墨绿、酒红、枣红、黑白、彩色、纯色、撞色、莫兰迪、大地色

6. 材质 (material): 棉、纯棉、丝、真丝、麻、亚麻、羊毛、羊绒、皮革、牛仔、雪纺、针织、毛呢、绒面、丝绒、涤纶、尼龙、莱卡、氨纶、天鹅绒、灯芯绒

7. 品类 (category): T恤、衬衫、卫衣、毛衣、针织衫、外套、大衣、风衣、羽绒服、棉服、西装、夹克、牛仔外套、皮衣、连衣裙、半身裙、长裙、短裙、A字裙、百褶裙、裤子、牛仔裤、休闲裤、西裤、阔腿裤、直筒裤、喇叭裤、短裤、打底裤、运动裤、背心、吊带、马甲

8. 场景 (occasion): 上班、通勤、约会、聚会、旅行、度假、运动、健身、逛街、日常、���家、派对、婚礼、面试、开学、毕业、拍照、出游、上学、职场

9. 身材 (body_type): 显瘦、显高、遮肉、小个子、高个子、微胖、梨形身材、苹果型、H型、A型、X型、沙漏型、宽肩、窄肩、长腿、短腿、粗腿、细腿

10. 价格 (price): 平价、高性价比、性价比、便宜、实惠、学生党、轻奢、高端、奢侈、大牌、小众、国货

请以 JSON 格式返回识别到的新标签：

```json
{{
  "style": ["标签1", "标签2"],
  "season": ["标签1"],
  "weather": [],
  "temperature": [],
  "color": ["标签1"],
  "material": [],
  "category": ["标签1"],
  "occasion": [],
  "body_type": [],
  "price": []
}}
```

只返回识别到的标签，空的类别可以省略。"""

            # 调用 LLM（超时见 config.llm_timeout_sec / get_llm_client）
            print(f"      [LLM API] 调用中...", flush=True)
            from langchain_core.output_parsers import StrOutputParser

            chain = self.claude_client | StrOutputParser()
            response_text = chain.invoke(prompt)
            print(f"      [LLM API] 调用完成", flush=True)

            # 解析响应
            # response_text 已经是字符串了

            # 提取 JSON
            try:
                if "```json" in response_text:
                    json_start = response_text.find("```json") + 7
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                elif "```" in response_text:
                    json_start = response_text.find("```") + 3
                    json_end = response_text.find("```", json_start)
                    json_text = response_text[json_start:json_end].strip()
                else:
                    json_text = response_text

                llm_tags = json.loads(json_text)

                # 过滤空值
                llm_tags = {k: v for k, v in llm_tags.items() if v}

                return llm_tags

            except json.JSONDecodeError:
                print(f"  ⚠️  LLM 标签识别 JSON 解析失败")
                return {}

        except Exception as e:
            print(f"  ⚠️  LLM 标签识别失败: {e}")
            return {}

    def analyze_posts(self, posts: List[Dict], use_llm_for_popular: bool = True) -> Dict:
        """
        分析多个帖子，统计标签分布

        Args:
            posts: 帖子列表
            use_llm_for_popular: 是否对热门帖子使用大模型识别

        Returns:
            标签分析结果
        """
        category_stats = defaultdict(lambda: defaultdict(int))
        all_categorized_tags = defaultdict(set)

        for i, post in enumerate(posts, 1):
            # 判断是否为热门帖子
            liked_count = post.get('liked_count', 0)
            collected_count = post.get('collected_count', 0)
            is_popular = liked_count > 1000 or collected_count > 500

            # 提取标签（热门帖子使用 LLM）
            use_llm = use_llm_for_popular and is_popular
            categorized = self.extract_from_post(post, use_llm=use_llm)

            if use_llm and is_popular:
                print(f"  [{i}] 热门帖子 (赞{liked_count}, 藏{collected_count}) - 使用 LLM 识别")

            for category, tags in categorized.items():
                for tag in tags:
                    category_stats[category][tag] += 1
                    all_categorized_tags[category].add(tag)

        # 转换为可序列化格式并排序
        result = {
            'total_posts': len(posts),
            'categories': {}
        }

        for category, tag_counts in category_stats.items():
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
            result['categories'][category] = {
                'total_unique_tags': len(sorted_tags),
                'tags': [{'tag': tag, 'count': count} for tag, count in sorted_tags]
            }

        return result

    def extract_knowledge_graph_data(self, posts: List[Dict], use_llm_for_popular: bool = True) -> Dict:
        """
        提取知识图谱所需的结构化数据

        Args:
            posts: 帖子列表
            use_llm_for_popular: 是否对热门帖子使用大模型识别

        Returns:
            知识图谱数据（节点和关系）
        """
        nodes = defaultdict(lambda: {'type': '', 'count': 0, 'posts': []})
        relationships = defaultdict(int)

        for post in posts:
            post_id = post.get('post_id', '')

            # 判断是否为热门帖子
            liked_count = post.get('liked_count', 0)
            collected_count = post.get('collected_count', 0)
            is_popular = liked_count > 1000 or collected_count > 500

            # 提取标签（热门帖子使用 LLM）
            use_llm = use_llm_for_popular and is_popular
            categorized = self.extract_from_post(post, use_llm=use_llm)

            # 创建节点
            for category, tags in categorized.items():
                for tag in tags:
                    node_id = f"{category}:{tag}"
                    nodes[node_id]['type'] = category
                    nodes[node_id]['count'] += 1
                    nodes[node_id]['posts'].append(post_id)

            # 创建关系（同一帖子中的标签之间有关联）
            all_tags = []
            for category, tags in categorized.items():
                for tag in tags:
                    all_tags.append(f"{category}:{tag}")

            # 两两组合创建关系
            for i in range(len(all_tags)):
                for j in range(i + 1, len(all_tags)):
                    rel_key = tuple(sorted([all_tags[i], all_tags[j]]))
                    relationships[rel_key] += 1

        # 转换为列表格式
        nodes_list = [
            {
                'id': node_id,
                'type': data['type'],
                'label': node_id.split(':')[1],
                'count': data['count'],
                'post_count': len(data['posts'])
            }
            for node_id, data in nodes.items()
        ]

        relationships_list = [
            {
                'source': rel[0],
                'target': rel[1],
                'weight': count
            }
            for rel, count in relationships.items()
            if count >= 2  # 只���留出现2次以上的关系
        ]

        return {
            'nodes': nodes_list,
            'relationships': relationships_list
        }


def analyze_clothing_data(json_file: str, output_file: str = None):
    """
    分析爬取的服装数据

    Args:
        json_file: 输入JSON文件路径
        output_file: 输出分析结果文件路径
    """
    print(f"正在加载数据: {json_file}")

    with open(json_file, 'r', encoding='utf-8') as f:
        posts = json.load(f)

    print(f"共加载 {len(posts)} 条帖子")

    # 创建提取器
    extractor = ClothingTagExtractor()

    # 分析标签
    print("\n正在分析标签...")
    analysis = extractor.analyze_posts(posts)

    # 提取知识图谱数据
    print("正在提取知识图谱数据...")
    kg_data = extractor.extract_knowledge_graph_data(posts)

    # 合并结果
    result = {
        'analysis': analysis,
        'knowledge_graph': kg_data
    }

    # 保存结果
    if output_file is None:
        output_file = json_file.replace('.json', '_analysis.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n分析结果已保存到: {output_file}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("标签分析摘要")
    print("=" * 60)

    for category, data in analysis['categories'].items():
        print(f"\n{category.upper()} ({data['total_unique_tags']} 个标签):")
        top_tags = data['tags'][:10]
        for item in top_tags:
            print(f"  {item['tag']}: {item['count']}")

    print(f"\n知识图谱统计:")
    print(f"  节点数: {len(kg_data['nodes'])}")
    print(f"  关系数: {len(kg_data['relationships'])}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python tag_extractor.py <json_file> [output_file]")
        print("示例: python tag_extractor.py clothing_data/clothing_posts_20260414.json")
        sys.exit(1)

    json_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    analyze_clothing_data(json_file, output_file)

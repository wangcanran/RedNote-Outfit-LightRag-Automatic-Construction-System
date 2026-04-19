"""
穿搭级别记录组织：context 来自文本标签；attributes 来自视觉侧每套 outfit（不再合并 image_analysis.tags）。
"""
from typing import Any, Dict, List


def context_from_text_tags(text_tags: Any) -> Dict[str, List]:
    """帖子级 context：仅从 tag_extractor 的 ai_extracted_tags 取季节/天气/温度/场景。"""
    if not isinstance(text_tags, dict):
        text_tags = {}
    return {
        "season": text_tags.get("season", []),
        "weather": text_tags.get("weather", []),
        "temperature": text_tags.get("temperature", []),
        "occasion": text_tags.get("occasion", []),
    }


def build_outfit_records(post: Dict, outfits: List[Dict], image_analysis: Dict) -> List[Dict]:
    """
    为每套穿搭构建独立的 JSON 记录

    Args:
        post: 原始帖子数据
        outfits: 识别出的穿搭列表
        image_analysis: 图片分析结果

    Returns:
        穿搭级别的 JSON 记录列表

    说明：
        每条 `items[]` 若含 **`garment_slot`**（top / bottom / shoe / accessory），
        会原样写入顶层记录；`kg_builder` 共现边优先使用该字段。
    """
    text_tags = post.get("ai_extracted_tags", {})
    post_level_tags = context_from_text_tags(text_tags)

    outfit_records = []

    for i, outfit in enumerate(outfits, 1):
        # 构建穿搭级别的记录
        outfit_record = {
            # 元数据
            'id': f"{post['post_id']}_outfit_{i}",
            'source_post_id': post['post_id'],
            'outfit_index': i,
            'outfit_total': len(outfits),

            # 帖子级别信息（所有穿搭共享）
            'post_info': {
                'title': post.get('title', ''),
                'author': post.get('author_nickname', ''),
                'url': post.get('post_url', ''),
                'crawl_time': post.get('crawl_time', ''),
            },

            # 帖子级别标签（季节/气候）
            'context': {
                'season': post_level_tags.get('season', []),
                'weather': post_level_tags.get('weather', []),
                'temperature': post_level_tags.get('temperature', []),
                'occasion': post_level_tags.get('occasion', [])
            },

            # 穿搭级别信息（每套不同）
            'outfit': {
                'index': i,
                'description': outfit.get('description', ''),
                'marker': outfit.get('marker', '')  # 左侧/中间/右侧
            },

            # 穿搭级别标签（颜色/材质/风格）
            'attributes': {
                'colors': outfit.get('colors', []),
                'materials': outfit.get('material', []),
                'styles': outfit.get('style', []),
                'categories': outfit.get('category', []),
                'body_types': outfit.get('body_type', [])
            },

            # 单品详情
            'items': outfit.get('items', []),

            # 原始数据引用
            'raw_data': {
                'image_analysis': image_analysis,
                'text_tags': text_tags
            }
        }

        outfit_records.append(outfit_record)

    return outfit_records


def merge_outfit_records(posts_with_outfits: List[tuple]) -> List[Dict]:
    """
    合并所有帖子的穿搭记录

    Args:
        posts_with_outfits: [(post, outfits, image_analysis), ...] 的列表

    Returns:
        所有穿搭的 JSON 记录列表
    """
    all_outfit_records = []

    for post, outfits, image_analysis in posts_with_outfits:
        records = build_outfit_records(post, outfits, image_analysis)
        all_outfit_records.extend(records)

    return all_outfit_records


# 示例输出格式
OUTFIT_RECORD_EXAMPLE = {
    "id": "6979dfba000000001a033aef_outfit_1",
    "source_post_id": "6979dfba000000001a033aef",
    "outfit_index": 1,
    "outfit_total": 3,

    "post_info": {
        "title": "早春就让男朋友这样穿，少年感满满",
        "author": "小野要早睡",
        "url": "https://www.xiaohongshu.com/explore/6979dfba000000001a033aef",
        "crawl_time": "2026-04-15T13:11:39.109348"
    },

    "context": {
        "season": ["春季", "早春"],
        "weather": ["晴天"],
        "temperature": ["15度"],
        "occasion": ["日常", "通勤"]
    },

    "outfit": {
        "index": 1,
        "description": "西装外套、白衬衫、黑色短裤、黑色短靴",
        "marker": "左侧"
    },

    "attributes": {
        "colors": ["灰色", "白色", "黑色"],
        "materials": ["棉", "牛仔"],
        "styles": ["简约", "通勤", "韩系"],
        "categories": ["西装", "衬衫", "短裤", "短靴"],
        "body_types": ["显瘦", "显高"]
    },

    "items": [
        {
            "category": "西装",
            "garment_slot": "top",
            "style": "修身",
            "colors": ["灰色"],
            "material": "棉",
            "details": {"fit": "修身"}
        }
    ],

    "raw_data": {
        "image_analysis": {},
        "text_tags": {}
    }
}

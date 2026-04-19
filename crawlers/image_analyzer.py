"""
服装图像分析模块
使用 VLM (Vision) 分析小红书服装图片
"""
import base64
import json
import os
import sys
from typing import Dict, List, Optional
from pathlib import Path
import requests

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import get_llm_client, get_model_name


class ClothingImageAnalyzer:
    """服装图像分析器 - 使用 Claude Vision"""

    def __init__(self):
        """初始化分析器"""
        self.client = get_llm_client()
        self.model_name = get_model_name()

        # 分析提示模板
        self.analysis_prompt = """请详细分析这张服装穿搭图片，提取以下信息：

1. **服装品类**：识别图片中的所有服装单品（如T恤、连衣裙、牛仔裤、外套等）
2. **款式细节**：描述每件服装的具体款式（如A字裙、阔腿裤、V领T恤等）
3. **颜色分析**：
   - 主色调
   - 配色方案
   - 颜色组合
4. **材质质感**：根据视觉判断材质（棉质、丝绸、牛仔、针织、雪纺等）
5. **风格特征**：整体穿搭风格（甜美、休闲、韩系、日系、正式、街头等）
6. **设计细节**：
   - 领口设计（圆领、V领、方领等）
   - 袖型（短袖、长袖、泡泡袖等）
   - 裙长/裤长
   - 版型（修身、宽松、oversize等）
7. **搭配方式**：上下装如何搭配，是否有配饰
8. **适用场景**：适合什么场合（通勤、约会、休闲、运动等）
9. **季节适配**：适合什么季节
10. **身材适配**：适合什么身材类型
11. **多套穿搭（重要）**：
    - 图中若只有**一套**完整搭配：`outfits` **可省略**，用顶层 `items` 列出这一套里的**所有单品**（一件穿搭里常有上衣、裤、鞋等多件，它们都属于同一套）。
    - 图中若为**拼图/左右对比/多格拼图**等，且存在**多套彼此独立**的完整搭配：请填写 **`outfits` 数组**，**每个元素代表一套穿搭**，每套内用 `items` 列该套的单品。**不要把同一套里的多个单品拆成多个 `outfits` 元素**（那会导致把单品误当成多套穿搭）。
12. **单品衣着位（必填）**：每个 `items` 元素必须包含 **`garment_slot`**，取值只能是 **`top`**（上装/外套等上身类）、**`bottom`**（裤/裙等下身类）、**`shoe`**（鞋靴）、**`accessory`**（包、表、帽、首饰、袜、腰带等非主体衣着）。连衣裙、连体类归为 **`bottom`**；无法判断时用 **`accessory`**。

请以 JSON 格式返回分析结果：

```json
{
  "categories": ["品类1", "品类2"],
  "items": [
    {
      "category": "品类名称",
      "garment_slot": "top",
      "style": "具体款式",
      "colors": ["颜色1", "颜色2"],
      "material": "材质",
      "details": {
        "neckline": "领口类型",
        "sleeve": "袖型",
        "length": "长度",
        "fit": "版型"
      }
    }
  ],
  "outfits": [
    {
      "label": "可选：左/第一套/上方",
      "description": "该套穿搭一句话描述",
      "overall_style": ["风格1"],
      "color_scheme": { "primary": "主色", "secondary": [], "combination": "" },
      "items": [ { "category": "单品", "garment_slot": "bottom", "style": "", "colors": [], "material": "", "details": {} } ]
    }
  ],
  "overall_style": ["风格1", "风格2"],
  "color_scheme": {
    "primary": "主色调",
    "secondary": ["辅助色1", "辅助色2"],
    "combination": "配色描述"
  },
  "outfit_combination": "搭配描述",
  "occasions": ["场景1", "场景2"],
  "seasons": ["季节1", "季节2"],
  "body_types": ["身材类型1", "身材类型2"],
  "tags": ["标签1", "标签2", "标签3"]
}
```

**仅一套穿搭时**可省略 `outfits` 或令 `outfits` 为单元素数组；`items` 与 `outfits[0].items` 勿重复罗列两套不同逻辑。

请确保返回有效的 JSON 格式。"""

    @staticmethod
    def _text_tags_consistency_block(
        text_tags: Optional[Dict],
        title: str = "",
        desc: str = "",
    ) -> str:
        """
        将 tag_extractor 产出的分类标签与标题/正文摘要拼成软提示，增强图文一致。
        模型被引导与文案对齐；若画面明显不符，仍以画面为准并在语义上协调输出。
        """
        chunks: List[str] = []
        t = (title or "").strip()
        d = (desc or "").strip()
        if t:
            chunks.append(f"标题摘录：{t[:240]}")
        if d:
            chunks.append(f"正文摘录：{d[:400]}")

        if isinstance(text_tags, dict) and text_tags:
            lines: List[str] = []
            for key, label in (
                ("season", "季节"),
                ("weather", "天气"),
                ("temperature", "温度"),
                ("occasion", "场景"),
                ("style", "风格"),
                ("color", "颜色"),
                ("material", "材质"),
                ("category", "品类"),
            ):
                vals = text_tags.get(key) or []
                if not isinstance(vals, (list, tuple)):
                    vals = [vals]
                vals = [str(v) for v in vals if v]
                if vals:
                    lines.append(f"- {label}：{', '.join(vals)}")
            if lines:
                chunks.append(
                    "从标题/正文/话题已提取的标签（请与画面交叉验证；"
                    "输出 JSON 时尽量与上述意图一致；若画面明显不符则以画面为准）：\n"
                    + "\n".join(lines)
                )

        if not chunks:
            return ""
        return "\n\n【图文一致性参考】\n" + "\n\n".join(chunks) + "\n"

    def _full_vision_prompt(
        self,
        text_tags: Optional[Dict] = None,
        title: str = "",
        desc: str = "",
    ) -> str:
        extra = self._text_tags_consistency_block(text_tags, title, desc)
        return self.analysis_prompt + extra

    def analyze_image_from_file(
        self,
        image_path: str,
        text_tags: Optional[Dict] = None,
        title: str = "",
        desc: str = "",
    ) -> Dict:
        """
        从本地文件分析图片（与 test_vision.py 一致：LangChain ChatOpenAI / ChatAnthropic + HumanMessage）

        Args:
            image_path: 本地图片路径
            text_tags: tag_extractor 产出的分类标签（可选），用于与画面对齐
            title: 帖子标题（可选）
            desc: 帖子正文（可选）

        Returns:
            分析结果，包含多套穿搭的列表
        """
        try:
            from langchain_core.messages import HumanMessage
            from langchain_core.output_parsers import StrOutputParser

            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            ext = Path(image_path).suffix.lower()
            media_type_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_type_map.get(ext, "image/jpeg")

            prompt_text = self._full_vision_prompt(text_tags, title, desc)

            message = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}",
                        },
                    },
                    {"type": "text", "text": prompt_text},
                ],
            )

            chain = self.client | StrOutputParser()
            result_text = chain.invoke([message])

            try:
                if "```json" in result_text:
                    json_start = result_text.find("```json") + 7
                    json_end = result_text.find("```", json_start)
                    json_text = result_text[json_start:json_end].strip()
                elif "```" in result_text:
                    json_start = result_text.find("```") + 3
                    json_end = result_text.find("```", json_start)
                    json_text = result_text[json_start:json_end].strip()
                else:
                    json_text = result_text

                analysis = json.loads(json_text)
                outfits = self._extract_outfits(analysis, result_text)

                return {"success": True, "analysis": analysis, "outfits": outfits}

            except json.JSONDecodeError:
                return {"success": False, "error": f"JSON 解析失败: {result_text[:100]}"}

        except FileNotFoundError:
            return {"success": False, "error": f"文件不存在: {image_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _extract_outfits(self, analysis: Dict, raw_text: str) -> List[Dict]:
        """
        提取穿搭列表。

        - 优先使用模型返回的 **`outfits`**（一图多套：拼图/对比等）。
        - 若无 `outfits` 或为空：视为**一套**，用顶层 `items`（一套里的多件单品，不是多套）。
        - 不再用「len(items) 条 = 多套」这种错误规则。
        """
        _ = raw_text

        blocks = analysis.get("outfits")
        if isinstance(blocks, list) and len(blocks) > 0:
            normalized: List[Dict] = []
            for i, block in enumerate(blocks, 1):
                if not isinstance(block, dict):
                    continue
                items = block.get("items")
                if not isinstance(items, list):
                    items = []
                desc = (block.get("description") or block.get("outfit_combination") or "").strip()
                sts = block.get("overall_style")
                if not isinstance(sts, list):
                    sts = list(analysis.get("overall_style") or [])
                colors = block.get("color_scheme")
                if not isinstance(colors, dict):
                    colors = dict(analysis.get("color_scheme") or {})
                cats = block.get("categories")
                if not isinstance(cats, list):
                    cats = list(analysis.get("categories") or [])
                if not desc:
                    desc = ", ".join(cats) if cats else f"穿搭{i}"
                label = block.get("label") or block.get("position") or block.get("marker")
                normalized.append(
                    {
                        "index": i,
                        "description": desc,
                        "marker": label or f"outfit_{i}",
                        "category": cats,
                        "style": sts,
                        "colors": colors,
                        "items": items,
                    }
                )
            if normalized:
                return normalized

        desc = (analysis.get("outfit_combination") or "").strip()
        if not desc:
            cats = analysis.get("categories", [])
            desc = ", ".join(cats) if isinstance(cats, list) else str(cats or "")

        return [
            {
                "index": 1,
                "description": desc,
                "marker": "full_image",
                "category": analysis.get("categories", []),
                "style": analysis.get("overall_style", []),
                "colors": analysis.get("color_scheme", {}),
                "items": analysis.get("items", []),
            }
        ]

    def analyze_image_from_url(
        self,
        image_url: str,
        text_tags: Optional[Dict] = None,
        title: str = "",
        desc: str = "",
    ) -> Dict:
        """
        通过图片 URL 分析（LangChain 多模态，与 test_vision.py 一致）。
        text_tags / title / desc 可选，用于图文一致性软提示。
        """
        try:
            from langchain_core.messages import HumanMessage
            from langchain_core.output_parsers import StrOutputParser

            prompt_text = self._full_vision_prompt(text_tags, title, desc)

            message = HumanMessage(
                content=[
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt_text},
                ],
            )
            chain = self.client | StrOutputParser()
            result_text = chain.invoke([message])

            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                json_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                json_text = result_text[json_start:json_end].strip()
            else:
                json_text = result_text

            analysis = json.loads(json_text)
            outfits = self._extract_outfits(analysis, result_text)
            return {"success": True, "analysis": analysis, "outfits": outfits}

        except json.JSONDecodeError:
            return {"success": False, "error": f"JSON 解析失败: {result_text[:200]}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_and_analyze(self, image_url: str, save_dir: str = "downloaded_images") -> Dict:
        """
        下载图片并分析

        Args:
            image_url: 图片 URL
            save_dir: 保存目录

        Returns:
            分析结果
        """
        try:
            # 创建保存目录
            os.makedirs(save_dir, exist_ok=True)

            # 下载图片
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()

            # 保存图片
            filename = f"{hash(image_url)}.jpg"
            filepath = os.path.join(save_dir, filename)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            # 分析图片
            result = self.analyze_image_from_file(filepath)
            result['image_path'] = filepath

            return result

        except Exception as e:
            return {
                'success': False,
                'error': f'Download failed: {e}'
            }

    def batch_analyze_urls(self, image_urls: List[str], max_images: int = 10) -> List[Dict]:
        """
        批量分析图片 URL

        Args:
            image_urls: 图片 URL 列表
            max_images: 最大分析数量

        Returns:
            分析结果列表
        """
        results = []

        for i, url in enumerate(image_urls[:max_images], 1):
            print(f"分析图片 {i}/{min(len(image_urls), max_images)}: {url[:50]}...")

            result = self.analyze_image_from_url(url)
            result['image_url'] = url
            results.append(result)

            # 避免请求过快
            if i < len(image_urls):
                import time
                time.sleep(1)

        return results


def enhance_post_with_image_analysis(post: Dict, analyzer: ClothingImageAnalyzer) -> Dict:
    """
    使用图像分析增强帖子数据

    Args:
        post: 原始帖子数据
        analyzer: 图像分析器

    Returns:
        增强后的帖子数据
    """
    enhanced_post = post.copy()

    # 获取封面图 URL
    cover_url = post.get('cover_url', '')

    if cover_url:
        print(f"分析帖子 {post.get('post_id', 'unknown')} 的图片...")

        # 分析图片
        image_result = analyzer.analyze_image_from_url(cover_url)

        if image_result.get('success'):
            analysis = image_result.get('analysis', {})

            # 添加图像分析结果
            enhanced_post['image_analysis'] = analysis

            # 合并标签
            original_tags = set(post.get('tags', []))
            image_tags = set(analysis.get('tags', []))
            enhanced_post['tags'] = list(original_tags | image_tags)

            # 添加视觉提取的信息
            enhanced_post['visual_categories'] = analysis.get('categories', [])
            enhanced_post['visual_styles'] = analysis.get('overall_style', [])
            enhanced_post['color_scheme'] = analysis.get('color_scheme', {})

            print(f"  ✓ 提取到 {len(analysis.get('items', []))} 个服装单品")
            print(f"  ✓ 识别风格: {', '.join(analysis.get('overall_style', []))}")

        else:
            print(f"  ✗ 图像分析失败: {image_result.get('error', 'Unknown error')}")
            enhanced_post['image_analysis_error'] = image_result.get('error')

    return enhanced_post


if __name__ == "__main__":
    # 测试图像分析
    print("=" * 60)
    print("服装图像分析测试")
    print("=" * 60)

    analyzer = ClothingImageAnalyzer()

    # 测试 URL（示例）
    test_url = input("\n请输入图片 URL（或按回车跳过）: ").strip()

    if test_url:
        print("\n正在分析图片...")
        result = analyzer.analyze_image_from_url(test_url)

        if result.get('success'):
            print("\n✓ 分析成功！")
            analysis = result['analysis']

            print(f"\n品类: {', '.join(analysis.get('categories', []))}")
            print(f"风格: {', '.join(analysis.get('overall_style', []))}")
            print(f"主色调: {analysis.get('color_scheme', {}).get('primary', 'N/A')}")
            print(f"适用场景: {', '.join(analysis.get('occasions', []))}")

            print("\n完整分析结果:")
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        else:
            print(f"\n✗ 分析失败: {result.get('error')}")
    else:
        print("\n跳过测试")

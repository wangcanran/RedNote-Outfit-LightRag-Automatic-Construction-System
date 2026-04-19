"""
批量标注模块 - 为爬取的数据添加标签
"""
import glob
import json
import os
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawlers.tag_extractor import ClothingTagExtractor
from crawlers.image_analyzer import ClothingImageAnalyzer
from outfit_organizer import build_outfit_records


def resolve_input_json_path(raw: str) -> str:
    """
    解析输入 JSON 路径。Windows PowerShell 不会展开 *.json，会把字面量传给脚本；
    若路径中含通配符 * ?，则用 glob 匹配；多个命中时取**最近修改**的一个并打印提示。

    爬虫默认把数据写在 crawlers/clothing_data/，若写 clothing_data/... 会优先尝试
    crawlers/clothing_data/...，避免通配符匹配不到。
    """
    raw = raw.strip().strip('"').strip("'")

    def under_crawlers(rel: str) -> str:
        return os.path.normpath(os.path.join("crawlers", rel))

    def try_resolve_non_glob(path: str) -> Optional[str]:
        p = os.path.normpath(path)
        if os.path.isfile(p):
            return p
        if not os.path.isabs(path):
            alt = under_crawlers(path)
            if os.path.isfile(alt):
                print(f"提示: 数据在 crawlers 目录下，已使用: {alt}")
                return alt
        return None

    if not any(ch in raw for ch in "*?["):
        r = try_resolve_non_glob(raw)
        return r if r is not None else raw

    patterns = [os.path.normpath(raw)]
    if not os.path.isabs(raw):
        rp = raw.replace("\\", "/").lstrip("./")
        if not rp.startswith("crawlers/"):
            patterns.append(under_crawlers(raw))

    matches: List[str] = []
    for pat in patterns:
        matches.extend(glob.glob(pat))
    matches = sorted(set(matches), key=lambda p: os.path.getmtime(p), reverse=True)
    if not matches:
        raise FileNotFoundError(
            f"通配符未匹配到任何文件: {raw}（已尝试: {patterns}）"
        )
    chosen = matches[0]
    if len(matches) > 1:
        print(
            f"提示: 通配符匹配到 {len(matches)} 个文件，使用最近修改的: {chosen}"
        )
    return chosen


def resolve_local_image_path(stored: Optional[str]) -> Optional[str]:
    """
    解析 JSON 里保存的本地图片路径。
    爬虫若在 crawlers/ 目录下运行，会写入 clothing_data/images/...，从项目根跑标注时
    实际文件在 crawlers/clothing_data/images/...，此处自动尝试 crawlers/ 前缀。
    """
    if not stored:
        return None
    p = os.path.normpath(stored)
    if os.path.isfile(p):
        return p
    if not os.path.isabs(p):
        alt = os.path.normpath(os.path.join("crawlers", p))
        if os.path.isfile(alt):
            return alt
    return None


def cap_posts_by_search_keyword(
    posts: List[Dict], max_per: Optional[int]
) -> List[Dict]:
    """
    按帖子字段 search_keyword 限额：每种关键词最多保留 max_per 条（保持 JSON 中的先后顺序）。
    无 search_keyword 的帖子归入同一组 ''。
    """
    if max_per is None or max_per <= 0:
        return posts
    counts: Dict[str, int] = defaultdict(int)
    out: List[Dict] = []
    for p in posts:
        sk = str(p.get("search_keyword") or "")
        if counts[sk] >= max_per:
            continue
        counts[sk] += 1
        out.append(p)
    return out


def split_multi_outfit_post(post: Dict, outfits: List[Dict]) -> List[Dict]:
    """
    如果一个帖子有多套穿搭，拆分成多条记录

    Args:
        post: 原始帖子
        outfits: 识别出的穿搭列表

    Returns:
        拆分后的帖子列表
    """
    if len(outfits) <= 1:
        return [post]

    split_posts = []
    for i, outfit in enumerate(outfits, 1):
        new_post = post.copy()
        new_post['post_id'] = f"{post['post_id']}_outfit_{i}"
        new_post['outfit_index'] = i
        new_post['outfit_total'] = len(outfits)
        new_post['outfit_data'] = outfit  # 单套穿搭的数据
        split_posts.append(new_post)

    return split_posts


class TagAnnotator:
    """标签标注器"""

    def __init__(
        self,
        enable_image_analysis: bool = False,
        align_vision_with_text: bool = True,
    ):
        """
        Args:
            enable_image_analysis: 是否启用图像分析
            align_vision_with_text: 是否将文本标签/标题/正文作为软提示传入视觉模型，增强图文一致性
        """
        self.tag_extractor = ClothingTagExtractor()
        self.image_analyzer = None
        self.enable_image_analysis = enable_image_analysis
        self.align_vision_with_text = align_vision_with_text

        if enable_image_analysis:
            self.image_analyzer = ClothingImageAnalyzer()
            print("✓ 图像分析已启用")
            if align_vision_with_text:
                print("✓ 视觉分析将参考文本标签（图文一致性）")

    def annotate_posts(self, posts: List[Dict], use_llm: bool = False) -> List[Dict]:
        """内存标注、不写盘（与 annotate_posts_incremental 逻辑一致，仅 output_path=None）。"""
        return self.annotate_posts_incremental(
            posts, use_llm=use_llm, output_path=None, initial_records=None
        )

    def annotate_posts_incremental(
        self,
        posts: List[Dict],
        use_llm: bool = False,
        output_path: Optional[str] = None,
        initial_records: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        批量标注，每处理完一篇帖子即写入 output_path（边标边存，便于断电续跑）。
        initial_records 为已存在的穿搭记录（续标时传入）；返回完整列表。
        """
        outfit_records: List[Dict] = list(initial_records or [])
        total_posts = len(posts)

        for i, post in enumerate(posts, 1):
            pid = post.get("post_id", "unknown")
            print(f"\n[{i}/{total_posts}] 标注帖子: {pid[:10]}… (post_id={pid})", flush=True)

            print(f"  [文本标签] 提取中...", flush=True)
            ai_tags = self.tag_extractor.extract_from_post(post, use_llm=use_llm)
            post["ai_extracted_tags"] = ai_tags
            tag_count = sum(len(v) for v in ai_tags.values())
            print(f"  [文本标签] 完成，提取 {tag_count} 个标签", flush=True)

            annotation_status = "ok"
            outfits: List[Dict] = []
            image_analysis: Dict = {}
            if self.enable_image_analysis and post.get("cover_local_path"):
                stored = post["cover_local_path"]
                local_path = resolve_local_image_path(stored)
                if local_path:
                    print(
                        f"  [图像分析] 分析中…（若久无响应多为 API 排队/超时，见 LLM_TIMEOUT_SEC）",
                        flush=True,
                    )
                    try:
                        if self.align_vision_with_text:
                            result = self.image_analyzer.analyze_image_from_file(
                                local_path,
                                text_tags=ai_tags,
                                title=post.get("title") or "",
                                desc=post.get("desc") or "",
                            )
                        else:
                            result = self.image_analyzer.analyze_image_from_file(
                                local_path
                            )
                        if result.get("success"):
                            image_analysis = result.get("analysis", {})
                            outfits = result.get("outfits", [])
                            print(
                                f"  [图像分析] 完成，识别 {len(outfits)} 套穿搭",
                                flush=True,
                            )
                        else:
                            annotation_status = "image_failed"
                            print(
                                f"  [图像分析] 失败: {result.get('error', 'Unknown')[:50]}",
                                flush=True,
                            )
                    except Exception as e:
                        annotation_status = "image_error"
                        print(f"  [图像分析] 异常: {e}", flush=True)
                else:
                    annotation_status = "image_missing"
                    print(
                        f"  [图像分析] 本地图片不存在: {stored} "
                        f"（已尝试项目根与 crawlers/ 下路径；请确认图片未删且与 JSON 同批爬取）",
                        flush=True,
                    )
            elif self.enable_image_analysis and not post.get("cover_local_path"):
                annotation_status = "no_cover_in_post"

            if not outfits:
                outfits = [
                    {
                        "index": 1,
                        "description": post.get("title", ""),
                        "marker": "default",
                    }
                ]

            records = build_outfit_records(post, outfits, image_analysis)
            for rec in records:
                rec["annotation_status"] = annotation_status
            outfit_records.extend(records)
            print(f"  [组织] 生成 {len(records)} 条穿搭记录", flush=True)

            if output_path:
                self.save_annotated_posts_atomic(outfit_records, output_path)
                print(
                    f"  [已保存] 累计 {len(outfit_records)} 条穿搭记录 → {output_path}",
                    flush=True,
                )

        print(
            f"\n✓ 本轮标注完成: {total_posts} 条帖子 → 累计 {len(outfit_records)} 条穿搭记录",
            flush=True,
        )
        return outfit_records

    @staticmethod
    def save_annotated_posts_atomic(posts: List[Dict], output_file: str) -> None:
        """原子写入：先写 .tmp 再替换，降低断电时主文件损坏概率。"""
        path = os.path.abspath(output_file)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(posts, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def save_annotated_posts(self, posts: List[Dict], output_file: str):
        """保存穿搭级别的记录（对外与原子写一致）"""
        self.save_annotated_posts_atomic(posts, output_file)
        print(f"✓ 穿搭记录已保存到: {output_file}")


def split_existing_for_resume(existing: List[Dict]) -> Tuple[List[Dict], Set[str], Set[str]]:
    """
    断点续标：仅把「标注成功」的帖子视为已完结；失败帖从文件中逻辑剔除后重标。

    返回 (保留的记录列表, 已完结的 post_id 集合, 因失败被剔除待重试的 post_id 集合)
    旧数据无 annotation_status 字段时视为 ok（兼容早期输出）。
    """
    by_post: Dict[str, List[Dict]] = defaultdict(list)
    for r in existing:
        sid = r.get("source_post_id")
        if sid:
            by_post[sid].append(r)

    retry_post_ids: Set[str] = set()
    for sid, recs in by_post.items():
        for r in recs:
            if r.get("annotation_status", "ok") != "ok":
                retry_post_ids.add(sid)
                break

    keep = [r for r in existing if r.get("source_post_id") not in retry_post_ids]
    done_ids = {r.get("source_post_id") for r in keep if r.get("source_post_id")}
    return keep, done_ids, retry_post_ids


def annotate_from_file(
    input_file: str,
    output_file: str = None,
    enable_image_analysis: bool = False,
    use_llm: bool = False,
    align_vision_with_text: bool = True,
    resume: bool = True,
    max_posts_per_search_keyword: Optional[int] = None,
):
    """
    从 JSON 文件读取爬取的数据，进行标注

    Args:
        input_file: 输入 JSON 文件（爬取的原始数据）
        output_file: 输出 JSON 文件（标注后的数据）
        enable_image_analysis: 是否启用图像分析
        use_llm: 是否使用大模型识别
        align_vision_with_text: 图像分析时是否传入文本标签与标题/正文摘要，增强图文一致性
        resume: 若输出文件已存在，是否跳过其中已出现的 source_post_id（断点续标）
        max_posts_per_search_keyword: 每个 search_keyword 最多标注多少条帖子（None 不限制）
    """
    input_file = resolve_input_json_path(input_file)

    if not os.path.isfile(input_file):
        raise FileNotFoundError(
            "找不到输入文件：\n"
            f"  {os.path.normpath(input_file)}\n"
            "请换成你本机真实存在的爬取结果 JSON。"
            "说明里的「xxx」只是占位示例，需改成实际文件名（例如 clothing_posts_20260416_005620.json）。"
        )

    if output_file is None:
        base = os.path.splitext(input_file)[0]
        output_file = f"{base}_annotated.json"
    output_file = os.path.normpath(output_file)

    print(f"读取数据: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        posts = json.load(f)
    print(f"✓ 读取 {len(posts)} 条帖子")

    if max_posts_per_search_keyword is not None:
        before = len(posts)
        posts = cap_posts_by_search_keyword(posts, max_posts_per_search_keyword)
        print(
            f"✓ 按 search_keyword 每词最多 {max_posts_per_search_keyword} 条："
            f" {before} → {len(posts)} 条"
        )

    existing_records: List[Dict] = []
    done_ids: Set[str] = set()
    if resume and os.path.isfile(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                raw_existing = json.load(f)
            if not isinstance(raw_existing, list):
                raw_existing = []
            existing_records, done_ids, retry_ids = split_existing_for_resume(
                raw_existing
            )
            print(
                f"✓ 断点续标：保留成功记录 {len(existing_records)} 条，"
                f"已完结 {len(done_ids)} 篇帖子将跳过"
            )
            if retry_ids:
                print(
                    f"✓ 此前标注非 ok 的 {len(retry_ids)} 篇已从进度中移除，将重新标注"
                )
        except json.JSONDecodeError as e:
            print(f"⚠️ 输出文件 JSON 损坏，将从头写入: {output_file}\n   {e}")
            existing_records, done_ids = [], set()
    elif not resume and os.path.isfile(output_file):
        print(f"提示: 已禁用续标（--fresh），将覆盖写入: {output_file}")

    orig_n = len(posts)
    posts = [p for p in posts if p.get("post_id") not in done_ids]
    print(f"待标注: {len(posts)} / {orig_n} 条帖子（已跳过 {orig_n - len(posts)}）")

    if not posts:
        print("没有新帖子需要标注。")
        return output_file

    annotator = TagAnnotator(
        enable_image_analysis=enable_image_analysis,
        align_vision_with_text=align_vision_with_text,
    )

    initial = [] if not resume else existing_records
    annotator.annotate_posts_incremental(
        posts,
        use_llm=use_llm,
        output_path=output_file,
        initial_records=initial,
    )

    return output_file


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python tag_annotation.py <input_json_file> [output_json_file] [选项...]")
        print("选项: [--image] [--llm] [--no-vision-text-align] [--fresh]")
        print("      [--max-per-keyword N]  每个 search_keyword 最多标注 N 条（需爬取 JSON 含该字段）")
        print("示例: python tag_annotation.py crawlers/clothing_data/clothing_posts_20260416_005620.json --image --llm")
        print("      python tag_annotation.py in.json out.json --llm --max-per-keyword 20")
        print("      默认：边标边存 + 同路径输出文件存在则断点续标（按 post_id 跳过已标帖子）")
        print("      --fresh ：忽略已有输出，从头标并覆盖写入")
        print("      --no-vision-text-align ：图像分析不参考文本标签")
        sys.exit(1)

    argv = sys.argv
    input_file = argv[1]
    output_file = argv[2] if len(argv) > 2 and not argv[2].startswith("--") else None

    max_per_kw: Optional[int] = None
    if "--max-per-keyword" in argv:
        i = argv.index("--max-per-keyword")
        if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            if argv[i + 1].isdigit():
                max_per_kw = int(argv[i + 1])

    enable_image = "--image" in argv
    use_llm = "--llm" in argv
    align_vision = "--no-vision-text-align" not in argv
    resume = "--fresh" not in argv

    print("=" * 60)
    print("服装标签批量标注工具")
    print("=" * 60)
    try:
        resolved = resolve_input_json_path(input_file)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
    if resolved != input_file:
        print(f"输入（原始）: {input_file}")
    print(f"输入文件: {resolved}")
    print(f"启用图像分析: {enable_image}")
    print(f"启用大模型识别: {use_llm}")
    print(f"视觉参考文本标签: {align_vision}")
    print(f"断点续标: {resume}（加 --fresh 则从头覆盖）")
    if max_per_kw is not None:
        print(f"每 search_keyword 最多: {max_per_kw} 条")
    print()

    try:
        annotate_from_file(
            resolved,
            output_file,
            enable_image_analysis=enable_image,
            use_llm=use_llm,
            align_vision_with_text=align_vision,
            resume=resume,
            max_posts_per_search_keyword=max_per_kw,
        )
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


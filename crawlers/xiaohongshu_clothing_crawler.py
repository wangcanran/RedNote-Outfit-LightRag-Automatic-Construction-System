"""
小红书服装标签爬虫
用于爬取构建知识图谱所需的服装相关标签：风格、天气、气温、季节、颜色、材质等
"""
import glob
import hashlib
import json
import os
import time
import csv
from datetime import datetime
from typing import List, Dict, Set, Optional, Any
from DrissionPage import ChromiumPage
import requests


class XiaohongshuClothingCrawler:
    """小红书服装标签爬虫"""

    # 跨批次去重指纹文件（与 clothing_posts_*.json 同目录，一行一个 SHA256 十六进制）
    DEDUP_MANIFEST_NAME = "crawl_seen_post_hashes.txt"

    # 预定义的搜索关键词（覆盖不同维度）
    SEARCH_KEYWORDS = [
        # 季节相关
        "春季穿搭", "夏季穿搭", "秋季穿搭", "冬季穿搭",
        # 风格相关
        "甜美风穿搭", "休闲风穿搭", "性感风穿搭", "正式穿搭", "通勤穿搭",
        "韩系穿搭", "日系穿搭", "欧美风穿搭", "复古风穿搭",
        # 天气相关
        "下雨天穿搭", "晴天穿搭", "阴天穿搭", "降温穿搭", "回暖穿搭",
        # 温度相关
        "10度穿搭", "15度穿搭", "20度穿搭", "25度穿搭", "30度穿搭",
        # 品类相关
        "连衣裙穿搭", "T恤穿搭", "牛仔裤穿搭", "卫衣穿搭", "西装穿搭",
    ]

    def __init__(
        self,
        output_dir: str = "clothing_data",
        only_cover_image: bool = False,
        max_posts_per_keyword: Optional[int] = None,
        dedup_from_history: bool = True,
    ):
        """
        初始化爬虫

        Args:
            output_dir: 数据输出目录
            only_cover_image: True 时只下载封面（第一张图），与 tag_annotation 仅用 cover 对齐，省流量与时间
            max_posts_per_keyword: 每个搜索词最多保留的帖子条数（去重后）；None 不限制。限额也可在 tag_annotation 用 --max-per-keyword
            dedup_from_history: True 时在开爬前加载本目录下历史批次指纹（manifest + clothing_posts*.json/csv），多批次运行不重复采集已出现过的帖子
        """
        self.output_dir = output_dir
        self.driver = None
        self.all_posts = []
        self.images_dir = os.path.join(output_dir, "images")
        self._debug_parse = False  # True 时打印 note / 图片解析调试信息
        self._only_cover_image = bool(only_cover_image)
        self._dedup_from_history = bool(dedup_from_history)
        # 全局去重：sha256(post_id)，跨关键词、跨批次（见 manifest）不重复采集
        self._seen_post_id_hashes: Set[str] = set()
        self._duplicate_skip_in_keyword: int = 0
        if max_posts_per_keyword is not None and max_posts_per_keyword <= 0:
            self._max_posts_per_keyword = None
        else:
            self._max_posts_per_keyword = max_posts_per_keyword

        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)

    def init_browser(self):
        """初始化浏览器"""
        print("正在初始化浏览器...")
        self.driver = ChromiumPage()
        # 监听小红书帖子接口
        self.driver.listen.start('https://edith.xiaohongshu.com/api/sns', method='POST')
        print("浏览器初始化完成")

    @staticmethod
    def _hash_post_id(post_id: str) -> str:
        """对帖子 ID 做 SHA256（十六进制），用作去重键与落库字段。"""
        raw = (post_id or "").strip()
        if not raw:
            return ""
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _ingest_post_row_for_dedup(self, row: Dict[str, Any]) -> None:
        """从历史 JSON/CSV 的一条记录提取指纹并加入去重集合。"""
        h = (row.get("post_id_hash") or "").strip().lower()
        if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
            self._seen_post_id_hashes.add(h)
            return
        pid = (row.get("post_id") or "").strip()
        if pid:
            key = self._hash_post_id(pid)
            if key:
                self._seen_post_id_hashes.add(key)

    def _load_historical_post_hashes(self) -> int:
        """
        从 output_dir 加载往期已采集帖子指纹：
        1) crawl_seen_post_hashes.txt（一行一个 SHA256，最快）
        2) clothing_posts*.json（无 hash 字段时从 post_id 现算）
        3) clothing_posts*.csv
        """
        manifest = os.path.join(self.output_dir, self.DEDUP_MANIFEST_NAME)
        if os.path.isfile(manifest):
            try:
                with open(manifest, "r", encoding="utf-8") as f:
                    for line in f:
                        h = line.strip().lower()
                        if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                            self._seen_post_id_hashes.add(h)
            except OSError as e:
                print(f"  [去重] 读取 manifest 失败: {e}")

        pattern_json = os.path.join(self.output_dir, "clothing_posts*.json")
        for path in sorted(glob.glob(pattern_json)):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    continue
                for row in data:
                    if isinstance(row, dict):
                        self._ingest_post_row_for_dedup(row)
            except (json.JSONDecodeError, OSError, TypeError):
                continue

        pattern_csv = os.path.join(self.output_dir, "clothing_posts*.csv")
        for path in sorted(glob.glob(pattern_csv)):
            try:
                with open(path, "r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row:
                            self._ingest_post_row_for_dedup(row)
            except OSError:
                continue

    def _save_dedup_manifest(self) -> None:
        """
        将当前内存中的指纹与磁盘上已有 manifest 合并后写回，
        便于下月爬取时跳过已采集帖子。
        """
        path = os.path.join(self.output_dir, self.DEDUP_MANIFEST_NAME)
        merged: Set[str] = set(self._seen_post_id_hashes)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        h = line.strip().lower()
                        if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                            merged.add(h)
            except OSError:
                pass
        try:
            with open(path, "w", encoding="utf-8") as f:
                for h in sorted(merged):
                    f.write(h + "\n")
            print(
                f"\n已更新跨批次去重库: {path}（共 {len(merged)} 条帖子指纹）"
            )
        except OSError as e:
            print(f"\n写入跨批次去重库失败: {e}")

    @staticmethod
    def _url_from_image_block(img: Dict) -> str:
        """从单张图的 JSON 块中取一条可用的图片 URL（优先清晰度较高的字段）。"""
        if not isinstance(img, dict):
            return ""
        for key in ("url_default", "url_large", "url", "url_mid", "url_small"):
            u = img.get(key)
            if isinstance(u, str) and u.strip():
                return u.strip()
        for info in img.get("info_list") or []:
            if not isinstance(info, dict):
                continue
            for key in ("url", "image_url", "url_default", "url_large"):
                u = info.get(key)
                if isinstance(u, str) and u.strip():
                    return u.strip()
        return ""

    def _collect_image_urls(self, note: Dict) -> List[str]:
        """
        收集笔记全部配图 URL（去重保序）。
        优先使用 image_list；若为空则回退到 cover。
        """
        seen: Set[str] = set()
        out: List[str] = []
        for img in note.get("image_list") or []:
            u = self._url_from_image_block(img if isinstance(img, dict) else {})
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        if not out:
            cover = note.get("cover")
            if isinstance(cover, dict):
                u = self._url_from_image_block(cover)
                if u:
                    out.append(u)
        return out

    def _ingest_search_response(
        self,
        json_data: Any,
        keyword: str,
        posts: List[Dict],
        cap: Optional[int],
    ) -> bool:
        """
        解析单次 sns 搜索响应中的 items；追加到 posts。
        按 post_id 的 SHA256 全局去重，已出现过的帖子跳过（不下载图片）。
        若已达到 max_posts_per_keyword 返回 True。
        """
        if not isinstance(json_data, dict):
            return cap is not None and len(posts) >= cap
        items = json_data.get("data", {}).get("items", [])
        for item in items:
            if cap is not None and len(posts) >= cap:
                return True

            post_data = self._parse_post(item, keyword)
            if not post_data:
                continue
            pid = (post_data.get("post_id") or "").strip()
            if not pid:
                continue
            pid_hash = self._hash_post_id(pid)
            if not pid_hash:
                continue
            if pid_hash in self._seen_post_id_hashes:
                self._duplicate_skip_in_keyword += 1
                continue
            self._seen_post_id_hashes.add(pid_hash)
            post_data["post_id_hash"] = pid_hash

            urls = post_data.get("image_urls") or []
            urls_to_save = urls[:1] if self._only_cover_image else urls
            if urls_to_save:
                local_paths = self._download_post_images(
                    urls_to_save, post_data["post_id"]
                )
                post_data["image_local_paths"] = local_paths
                post_data["cover_local_path"] = local_paths[0] if local_paths else None
                if local_paths:
                    hint = "（仅封面）" if self._only_cover_image else ""
                    print(
                        f"      [下载图片] {post_data.get('post_id', 'unknown')[:10]}: "
                        f"{len(local_paths)} 张{hint} -> {self.images_dir}"
                    )

            post_data["image_download_mode"] = (
                "cover_only" if self._only_cover_image else "all"
            )
            posts.append(post_data)

        return cap is not None and len(posts) >= cap

    def search_and_scroll(self, keyword: str, scroll_times: int = 10) -> List[Dict]:
        """
        搜索关键词并滚动页面获取数据

        Args:
            keyword: 搜索关键词
            scroll_times: 滚动次数

        Returns:
            帖子数据列表
        """
        print(f"\n开始搜索关键词: {keyword}")

        # 访问小红书首页
        self.driver.get('https://www.xiaohongshu.com/')
        time.sleep(3)

        # 搜索
        self.driver.ele('#search-input').input(keyword)
        self.driver.ele('.search-icon').click()
        time.sleep(3)

        posts: List[Dict] = []
        cap = self._max_posts_per_keyword
        self._duplicate_skip_in_keyword = 0

        # 滚动拉取（使用平台默认搜索结果排序，不点筛选/排序）
        for i in range(scroll_times):
            if cap is not None and len(posts) >= cap:
                print(f"  已达本关键词上限 {cap} 条，停止滚动")
                break

            print(f'  滚动 {i + 1}/{scroll_times}...')
            self.driver.scroll.to_bottom()
            time.sleep(2)

            resp = self.driver.listen.wait(timeout=5)

            if not resp:
                print(f'  第{i + 1}次滚动未获取到数据')
                continue

            try:
                json_data = resp.response.body
                items = json_data.get('data', {}).get('items', [])
                self._ingest_search_response(
                    json_data, keyword, posts, cap
                )
                print(f'  获取到 {len(items)} 条数据')
                if cap is not None and len(posts) >= cap:
                    print(f"  已达本关键词上限 {cap} 条，停止滚动")
                    break

            except Exception as e:
                print(f'  解析数据失败: {e}')

        msg = f"关键词 '{keyword}' 共获取 {len(posts)} 条帖子" + (
            f"（上限 {cap}）" if cap else ""
        )
        if self._duplicate_skip_in_keyword:
            msg += f"，跳过全局重复 {self._duplicate_skip_in_keyword} 条"
        print(msg)
        return posts

    def _parse_post(self, item: Dict, search_keyword: str) -> Dict:
        """
        解析单条帖子数据，提取标签信息

        Args:
            item: 原始帖子数据
            search_keyword: 搜索关键词

        Returns:
            解析后的帖子数据
        """
        try:
            note = item.get('note_card', {})
            if not note:
                return None

            post_id = item.get('id', '')
            # 搜索流里常见 display_title；部分接口只有 title / 标题在 desc 里
            title = (
                (note.get("display_title") or note.get("title") or "")
                .strip()
            )
            desc = (
                (note.get("desc") or note.get("description") or "")
                .strip()
            )

            # 用户信息
            user = note.get('user', {})
            nickname = user.get('nickname', '')
            user_id = user.get('user_id', '')

            # 互动数据
            interact_info = note.get('interact_info', {})
            liked_count = interact_info.get('liked_count', 0)
            collected_count = interact_info.get('collected_count', 0)
            comment_count = interact_info.get('comment_count', 0)

            # 标签信息（重要！）
            tags = []
            tag_list = note.get('tag_list', [])
            for tag in tag_list:
                if isinstance(tag, dict):
                    tags.append(tag.get('name', ''))
                elif isinstance(tag, str):
                    tags.append(tag)

            image_urls = self._collect_image_urls(note)
            cover_url = image_urls[0] if image_urls else ""

            if self._debug_parse and not hasattr(self, "_debug_note_keys_printed"):
                print(f"[DEBUG] note 键: {list(note.keys())}, 图片数: {len(image_urls)}")
                self._debug_note_keys_printed = True

            # 帖子类型
            note_type = note.get('type', 'normal')  # normal/video

            # 构建帖子URL
            post_url = f'https://www.xiaohongshu.com/explore/{post_id}' if post_id else ''

            return {
                'post_id': post_id,
                'title': title,
                'desc': desc,
                'tags': tags,  # 标签列表
                'search_keyword': search_keyword,  # 搜索关键词
                'author_nickname': nickname,
                'author_id': user_id,
                'liked_count': liked_count,
                'collected_count': collected_count,
                'comment_count': comment_count,
                'cover_url': cover_url,
                'image_urls': image_urls,
                'cover_local_path': None,
                'image_local_paths': [],
                'note_type': note_type,
                'post_url': post_url,
                'crawl_time': datetime.now().isoformat(),
                'ai_extracted_tags': {}  # 初始化 AI 提取的标签
            }

        except Exception as e:
            print(f'  解析帖子失败: {e}')
            import traceback
            traceback.print_exc()
            return None

    def crawl_by_keywords(self, keywords: List[str] = None, scroll_times: int = 10):
        """
        按关键词列表批量爬取

        Args:
            keywords: 关键词列表，默认使用预定义关键词
            scroll_times: 每个关键词滚动次数（达到 max_posts_per_keyword 会提前结束）
        """
        if keywords is None:
            keywords = self.SEARCH_KEYWORDS

        if self._max_posts_per_keyword:
            print(
                f"每个关键词最多采集 {self._max_posts_per_keyword} 条帖子（去重后）"
            )

        self.init_browser()

        if self._dedup_from_history:
            self._load_historical_post_hashes()
            total = len(self._seen_post_id_hashes)
            if total:
                print(
                    f"历史去重：已从 {self.output_dir} 加载 {total} 条帖子指纹，"
                    "将跳过往期已采集笔记"
                )
            else:
                print("历史去重：未找到往期数据，将全量尝试采集")

        for idx, keyword in enumerate(keywords, 1):
            print(f"\n[{idx}/{len(keywords)}] 处理关键词: {keyword}")

            try:
                posts = self.search_and_scroll(keyword, scroll_times)
                self.all_posts.extend(posts)

                # 每个关键词之间休息一下，避免被限流
                if idx < len(keywords):
                    wait_time = 5
                    print(f"等待 {wait_time} 秒后继续...")
                    time.sleep(wait_time)

            except Exception as e:
                print(f"处理关键词 '{keyword}' 时出错: {e}")
                continue

        print(f"\n爬取完成！共获取 {len(self.all_posts)} 条帖子数据")
        self._save_dedup_manifest()

    def save_to_csv(self, filename: str = None):
        """保存数据到CSV"""
        if not self.all_posts:
            print("没有数据可保存")
            return

        if filename is None:
            filename = f"clothing_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = [
                'post_id', 'post_id_hash', 'title', 'desc', 'tags', 'search_keyword',
                'author_nickname', 'author_id', 'liked_count', 'collected_count',
                'comment_count', 'cover_url', 'image_urls', 'image_download_mode',
                'cover_local_path', 'image_local_paths', 'note_type', 'post_url',
                'crawl_time',
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for post in self.all_posts:
                row = {k: post.get(k) for k in fieldnames}
                row['tags'] = '|'.join(post.get('tags') or [])
                row['image_urls'] = '|'.join(post.get('image_urls') or [])
                paths = post.get('image_local_paths') or []
                row['image_local_paths'] = '|'.join(paths) if paths else ''
                writer.writerow(row)

        print(f"数据已保存到: {filepath}")

    def save_to_json(self, filename: str = None):
        """保存数据到JSON（用于LightRAG）"""
        if not self.all_posts:
            print("没有数据可保存")
            return

        if filename is None:
            filename = f"clothing_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.all_posts, f, ensure_ascii=False, indent=2)

        print(f"JSON数据已保存到: {filepath}")

    def extract_tags_summary(self) -> Dict:
        """
        提取标签统计摘要（用于了解数据分布）

        Returns:
            标签统计字典
        """
        tag_count = {}

        for post in self.all_posts:
            for tag in post.get('tags', []):
                if tag:
                    tag_count[tag] = tag_count.get(tag, 0) + 1

        # 按频次排序
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)

        return {
            'total_posts': len(self.all_posts),
            'total_unique_tags': len(tag_count),
            'top_20_tags': sorted_tags[:20]
        }

    def save_tags_summary(self, filename: str = "tags_summary.json"):
        """保存标签统计摘要"""
        summary = self.extract_tags_summary()
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n标签统计摘要:")
        print(f"  总帖子数: {summary['total_posts']}")
        print(f"  唯一标签数: {summary['total_unique_tags']}")
        print(f"  Top 20 标签:")
        for tag, count in summary['top_20_tags']:
            print(f"    {tag}: {count}")

        print(f"\n摘要已保存到: {filepath}")

    _REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.xiaohongshu.com/",
    }

    def _download_one_image(self, image_url: str, filepath: str) -> bool:
        """下载单张图到指定路径。"""
        if not image_url:
            return False
        try:
            response = requests.get(
                image_url, timeout=15, headers=self._REQUEST_HEADERS
            )
            if response.status_code != 200:
                return False
            with open(filepath, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            print(f"      [下载图片] 失败: {e}")
            return False

    def _download_post_images(self, image_urls: List[str], post_id: str) -> List[str]:
        """
        下载帖子全部配图。文件名：{post_id}_0.jpg, {post_id}_1.jpg, ...
        """
        if not post_id or not image_urls:
            return []
        os.makedirs(self.images_dir, exist_ok=True)
        saved: List[str] = []
        for idx, url in enumerate(image_urls):
            ext = ".jpg"
            if ".webp" in url.lower():
                ext = ".webp"
            filename = f"{post_id}_{idx}{ext}"
            filepath = os.path.join(self.images_dir, filename)
            if self._download_one_image(url, filepath):
                saved.append(filepath)
            time.sleep(0.15)
        return saved

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("浏览器已关闭")


def main():
    """主函数"""
    print("=" * 60)
    print("小红书服装标签爬虫")
    print("=" * 60)

    # 选择模式
    print("\n请选择爬取模式:")
    print("1. 使用预定义关键词（推荐）")
    print("2. 自定义关键词")

    choice = input("请输入选项 (1/2): ").strip()

    if choice == "2":
        keywords_input = input("请输入关键词（用逗号分隔）: ")
        keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
    else:
        keywords = None  # 使用默认关键词

    scroll_times = input("每个关键词滚动次数 (默认10): ").strip()
    scroll_times = int(scroll_times) if scroll_times.isdigit() else 10

    max_posts_in = input(
        "每个关键词最多帖子数 (直接回车=不限制；或填数字如 20): "
    ).strip()
    if max_posts_in == "" or max_posts_in == "0":
        max_posts_per_keyword = None
    elif max_posts_in.isdigit():
        max_posts_per_keyword = int(max_posts_in)
    else:
        max_posts_per_keyword = None

    only_cover = (
        input("仅下载封面图? y/N（默认 N；y 省流量，与 tag_annotation 单图分析一致）: ")
        .strip()
        .lower()
        == "y"
    )

    dedup_hist = input(
        "与历史批次去重（不重复爬取往期已保存的帖子，适合每月增量爬）? Y/n（默认 Y）: "
    ).strip().lower()
    dedup_from_history = dedup_hist not in ("n", "no")

    crawler = XiaohongshuClothingCrawler(
        output_dir="clothing_data",
        only_cover_image=only_cover,
        max_posts_per_keyword=max_posts_per_keyword,
        dedup_from_history=dedup_from_history,
    )

    try:
        # 开始爬取
        crawler.crawl_by_keywords(keywords=keywords, scroll_times=scroll_times)

        # 保存数据
        crawler.save_to_csv()
        crawler.save_to_json()
        crawler.save_tags_summary()

        print("\n" + "=" * 60)
        print("爬取完成！")
        print("=" * 60)
        print("\n下一步：运行标注工具")
        print(f"python tag_annotation.py clothing_data/clothing_posts_*.json --image --llm")

    except KeyboardInterrupt:
        print("\n\n用户中断爬取")
    except Exception as e:
        print(f"\n爬取过程出错: {e}")
    finally:
        crawler.close()

    print("\n" + "=" * 60)
    print("爬取完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

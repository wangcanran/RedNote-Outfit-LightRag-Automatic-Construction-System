import json
import os
import time
import csv
from DrissionPage import ChromiumPage
 
# 初始化浏览器
driver = ChromiumPage()
 
# 监听小红书帖子接口（关键！精准获取数据）
driver.listen.start('https://edith.xiaohongshu.com/api/sns', method='POST')

a = input('请输入想要采集的视频信息：')
# 访问小红书首页
driver.get('https://www.xiaohongshu.com/')
time.sleep(3)  # 等待页面加载
 
# 在搜索框输入关键词并点击搜索
driver.ele('#search-input').input(f'{a}')  # 定位搜索框并输入关键词
driver.ele('.search-icon').click()  # 点击搜索按钮
time.sleep(3)

scroll_times = 13  # 滚动13次（可根据需求调整）
 
for i in range(scroll_times):
    print(f'正在执行第{i + 1}次滚动...')
    driver.scroll.to_bottom()  # 滚动到页面底部
    time.sleep(2)  # 等待数据加载
 
    # 等待接口返回（超时5秒，避免卡死）
    resp = driver.listen.wait(timeout=5)
 
    if not resp:
        print(f'第{i + 1}次滚动未监听到接口数据，跳过。')
        continue
    
    # 解析接口返回的JSON数据
    try:
        json_data = resp.response.body  # 获取响应体（JSON格式）
        print(f'第{i+1}次滚动获取到数据：{json_data}')
    except Exception as e:
        print(f'解析响应失败: {e}')

# 创建“视频信息”文件夹（如果不存在）
if not os.path.exists('视频信息'):
    os.makedirs('视频信息')
 
csv_path = f'视频信息/谷子.csv'  # CSV文件路径（可自定义名称）

# 从JSON中提取需要的字段
items = json_data.get('dat', {}).get('items', [])  # 帖子列表
 
# 写入CSV（首次写入时添加表头）
write_header = not os.path.exists(csv_path)  # 判断是否需要写表头
 
with open(csv_path, 'a+', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    if write_header:
        # 表头：帖子ID、标题、作者昵称、点赞数等
        writer.writerow([
            '帖子ID', '标题', '昵称', '用户ID', '用户头像URL',
            '点赞数', '封面图URL（默认）', '封面图URL（高清）', '视频链接'
        ])
    
    # 遍历每一条帖子数据
    for item in items:
        note = item.get('note_card', {})  # 帖子核心信息
        if not note:
            continue
        
        # 提取字段（根据JSON结构逐层获取）
        post_id = item.get('id', '')  # 帖子ID
        title = note.get('disply_title', '').strip()  # 标题
        nickname = note.get('user', {}).get('nickname', '')  # 作者昵称
        liked_count = note.get('interact_info', {}).get('liked_count', '0')  # 点赞数
        # 视频链接（小红书视频链接格式：https://www.xiaohongshu.com/explore/帖子ID）
        video_url = f'https://www.xiaohongshu.com/explore/{post_id}' if post_id else ''
        
        # 写入CSV行
        writer.writerow([
            post_id, title, nickname, user_id, avatar,
            liked_count, cover_url_default, cover_url_pre, video_url
        ])

# 将原始JSON写入文件（方便后续分析）
with open('视频信息/1.json', 'a+', encoding='utf-8-sig') as f:
    json.dump(json_data, f, ensure_ascii=False)
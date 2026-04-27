import requests
import pandas as pd
import time
import os
import re
from typing import List, Dict, Optional
from tqdm import tqdm

# ===================== 配置项 =====================
DEFAULT_BVID_LIST = [
    "BV1LXwyzkEqo",
]
REQUEST_INTERVAL = 2
RETRY_TIMES = 3
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/"
}

# ===================== BV号校验 =====================
def validate_bvid(bvid: str) -> Optional[str]:
    """校验BV号格式，有效则返回标准化BV号，无效返回None"""
    bvid = bvid.strip()
    bv_match = re.search(r"BV[a-zA-Z0-9]{10}", bvid)
    if not bv_match:
        return None
    standard_bvid = bv_match.group()
    return standard_bvid if len(standard_bvid) == 12 else None

# ===================== 文件读取 =====================
def load_bvid_from_file(file_path: str) -> List[str]:
    """从文件读取BV号，返回去重后的有效BV号列表"""
    if not os.path.exists(file_path):
        print(f"❌ 错误：文件 {file_path} 不存在")
        return []
    
    file_ext = os.path.splitext(file_path)[1].lower()
    raw_bvid_list = []

    try:
        if file_ext == ".txt":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="gbk") as f:
                    content = f.read()
            raw_bvid_list = re.split(r"[\s,\n]+", content.strip())
        
        elif file_ext == ".csv":
            df = pd.read_csv(file_path, encoding="utf-8-sig")
            for col in df.columns:
                raw_bvid_list.extend(df[col].astype(str).tolist())
        
        elif file_ext in [".xlsx", ".xls"]:
            try:
                import openpyxl
            except ImportError:
                print("❌ 错误：需安装openpyxl，请执行：pip install openpyxl")
                return []
            df = pd.read_excel(file_path)
            for col in df.columns:
                raw_bvid_list.extend(df[col].astype(str).tolist())
        
        else:
            print(f"❌ 错误：不支持 {file_ext}，仅支持 .txt/.csv/.xlsx/.xls")
            return []

    except Exception as e:
        print(f"❌ 文件读取失败：{str(e)}")
        return []

    valid_bvid_list = list({validate_bvid(item) for item in raw_bvid_list if validate_bvid(item)})
    print(f"{'✅' if valid_bvid_list else '⚠️'} 成功读取到 {len(valid_bvid_list)} 个有效BV号（已去重）" if valid_bvid_list else "⚠️  警告：文件中未找到有效BV号")
    return valid_bvid_list

# ===================== 视频抓取 =====================
def get_video_data(bvid: str) -> Optional[Dict]:
    """抓取单个视频的核心数据"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    for retry in range(RETRY_TIMES):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data["code"] != 0:
                print(f"❌ 抓取失败 {bvid}：{data.get('message', '视频不存在')}")
                return None
            
            stat = data["data"]["stat"]
            video_info = {
                "bvid": bvid,
                "title": data["data"]["title"],
                "up主": data["data"]["owner"]["name"],
                "播放量": stat["view"],
                "弹幕数": stat["danmaku"],
                "评论数": stat["reply"],
                "收藏数": stat["favorite"],
                "投币数": stat["coin"],
                "点赞数": stat["like"],
                "分享数": stat["share"],
                "抓取时间": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            print(f"✅ 成功抓取：{bvid} | {video_info['title']}")
            return video_info
        
        except Exception as e:
            print(f"⚠️  第 {retry+1} 次抓取失败 {bvid}：{str(e)}，重试中...")
            time.sleep(REQUEST_INTERVAL)
    
    print(f"❌ 最终抓取失败 {bvid}：已达最大重试次数")
    return None

def batch_fetch_videos(bvid_list: List[str]) -> pd.DataFrame:
    """批量抓取视频数据"""
    if not bvid_list:
        print("❌ 无有效BV号，抓取终止")
        return pd.DataFrame()
    
    video_data_list = []
    total = len(bvid_list)
    print(f"\n开始批量抓取，共 {total} 个视频")
    print("="*50)

    for bvid in tqdm(bvid_list, desc="抓取进度", unit="视频"):
        video_data = get_video_data(bvid)
        if video_data:
            video_data_list.append(video_data)
        time.sleep(REQUEST_INTERVAL)
    
    print("\n" + "="*50)
    print(f"抓取完成：成功 {len(video_data_list)} 个，失败 {total - len(video_data_list)} 个")
    
    if video_data_list:
        df = pd.DataFrame(video_data_list)
        file_name = f"{time.strftime('%Y%m%d')}_specified_video_data.csv"
        df.to_csv(file_name, index=False, encoding="utf-8-sig")
        print(f"数据已保存至：{file_name}")
        return df
    else:
        print("❌ 无有效数据，未生成CSV文件")
        return pd.DataFrame()

# ===================== 排行榜计算 =====================
def calculate_rank_and_score(last_file: str, current_file: str):
    """计算增量、得分并生成排行榜"""
    try:
        df_last = pd.read_csv(last_file, encoding="utf-8-sig")
        df_current = pd.read_csv(current_file, encoding="utf-8-sig")
    except Exception as e:
        print(f"❌ 文件读取失败：{str(e)}")
        return
    
    required_cols = ["bvid", "title", "up主", "播放量", "弹幕数", "评论数", "收藏数", "投币数", "点赞数"]
    for col in required_cols:
        if col not in df_last.columns or col not in df_current.columns:
            print(f"❌ CSV文件缺少必要列：{col}")
            return
    
    df_merge = pd.merge(df_last, df_current, on="bvid", suffixes=("_上期", "_本期"), how="inner")
    if df_merge.empty:
        print("❌ 两期数据无匹配的BV号")
        return
    
    # 计算增量
    cols = ["播放", "弹幕", "评论", "收藏", "投币", "点赞"]
    for col in cols:
        df_merge[f"{col}增量"] = (df_merge[f"{col}数_本期"] - df_merge[f"{col}数_上期"]).clip(lower=0)
    
    # 计分规则
    df_merge["点赞有效增量"] = df_merge.apply(lambda x: min(x["点赞增量"], x["投币增量"] * 2), axis=1)
    A = B = C = D = 1
    
    df_merge["播放得分"] = df_merge["播放增量"] * D
    df_merge["互动得分"] = (df_merge["评论增量"] + df_merge["弹幕增量"]) * A * 15
    df_merge["收藏得分"] = df_merge["收藏增量"] * B
    df_merge["投币得分"] = df_merge["投币增量"] * C
    df_merge["点赞得分"] = df_merge["点赞有效增量"]
    df_merge["最终得分"] = df_merge["播放得分"] + df_merge["互动得分"] + df_merge["收藏得分"] + df_merge["投币得分"] + df_merge["点赞得分"]
    
    # 排序并保存
    df_rank = df_merge.sort_values("最终得分", ascending=False).reset_index(drop=True)
    df_rank.insert(0, "排名", df_rank.index + 1)
    
    result_file = "specified_rank_result.csv"
    df_rank[["排名", "bvid", "title_本期", "up主_本期", "最终得分", "播放增量", "弹幕增量", "评论增量", "收藏增量", "投币增量", "点赞有效增量"]].to_csv(
        result_file, index=False, encoding="utf-8-sig"
    )
    
    print("\n" + "="*50)
    print("📊 排行榜生成完成，预览TOP10：")
    print(df_rank[["排名", "bvid", "title_本期", "up主_本期", "最终得分"]].head(10).to_string(index=False))
    print("="*50)
    print(f"完整排行榜已保存至：{result_file}")

# ===================== 主菜单 =====================
def menu():
    print("\n" + "="*50)
    print("虚拟歌手中文曲排行榜 特定视频抓取&计分工具")
    print("="*50)
    print("1. 抓取指定BV号的视频数据并保存")
    print("2. 计算增量、得分并生成排行榜")
    print("3. 退出")
    print("="*50)
    return input("请输入操作序号：").strip()

def input_bvid_list() -> List[str]:
    print("\n请选择BV号输入模式：")
    print("1. 使用脚本预设的BV号列表")
    print("2. 手动输入BV号")
    print("3. 从文件批量导入BV号")
    mode_choice = input("请输入模式序号：").strip()

    if mode_choice == "1":
        target_bvid_list = [bv for bv in DEFAULT_BVID_LIST if validate_bvid(bv)]
        print(f"✅ 加载预设列表，共 {len(target_bvid_list)} 个有效BV号")
        return target_bvid_list
    elif mode_choice == "2":
        input_str = input("请输入要抓取的BV号，多个BV号用空格分隔：").strip()
        return [bv for bv in input_str.split() if validate_bvid(bv)]
    elif mode_choice == "3":
        file_path = input("请输入BV号文件路径（如 bv_list.txt）：").strip()
        return load_bvid_from_file(file_path)
    else:
        print("❌ 无效的模式序号")
        return []

def main():
    while True:
        choice = menu()
        
        if choice == "1":
            target_bvid_list = input_bvid_list()
            if target_bvid_list:
                batch_fetch_videos(target_bvid_list)
            else:
                print("❌ 无有效BV号，抓取终止")
        
        elif choice == "2":
            last_file = input("请输入上期数据CSV文件名：").strip()
            current_file = input("请输入本期数据CSV文件名：").strip()
            calculate_rank_and_score(last_file, current_file)
        
        elif choice == "3":
            print("👋 程序已退出")
            break
        
        else:
            print("❌ 无效的操作序号")

if __name__ == "__main__":
    main()

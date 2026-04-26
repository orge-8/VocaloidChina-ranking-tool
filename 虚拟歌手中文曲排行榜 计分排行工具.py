
import requests
import time
import pandas as pd
from datetime import datetime
from typing import List, Dict
# ====================== 【指定BV号配置区】可直接在这里修改要抓取的视频 ======================
# 预设要抓取的BV号列表，一行一个，格式："BVxxxxxx"，用英文逗号分隔
DEFAULT_BVID_LIST = [
    "BV1LXwyzkEqo",
    "BV1W9DUBME3W",
    # 在这里继续添加你要抓取的BV号
]
# ==============================================================================================


# ====================== 全局配置（无需修改，保持默认即可）======================
REQUEST_INTERVAL = 2  # 请求间隔（秒，控制频率避免被限流，建议不小于1）
RETRY_TIMES = 3       # 失败重试次数
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*"
}


# ====================== 1. 抓取指定BV号的视频完整数据 ======================
def get_specified_video_data(bvid_list: List[str]) -> pd.DataFrame:
    """
    抓取指定BV号的视频基础信息+统计数据
    :param bvid_list: BV号列表
    :return: 视频数据DataFrame
    """
    video_list = []
    total = len(bvid_list)
    print(f"开始抓取，共{total}个指定BV号...")
    for idx, bvid in enumerate(bvid_list, 1):
        print(f"[{idx}/{total}] 正在抓取 {bvid}...")
        if not isinstance(bvid, str) or not bvid.startswith("BV") or len(bvid) != 12:
            print(f"跳过无效BV号：{bvid}（格式错误）")
            continue
        retry_count = 0
        while retry_count < RETRY_TIMES:
            try:
                url = "https://api.bilibili.com/x/web-interface/view"
                params = {"bvid": bvid}
                resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
                resp.raise_for_status()
                result = resp.json()
                if result["code"] == 0:
                    video_data = result["data"]
                    stat_data = video_data["stat"]
                    video_list.append({
                        "bvid": bvid,
                        "title": video_data["title"],
                        "author": video_data["owner"]["name"],
                        "duration": video_data["duration"],
                        "pubdate": datetime.fromtimestamp(video_data["pubdate"]).strftime("%Y-%m-%d %H:%M:%S"),
                        "view": stat_data["view"],
                        "danmaku": stat_data["danmaku"],
                        "reply": stat_data["reply"],
                        "favorite": stat_data["favorite"],
                        "coin": stat_data["coin"],
                        "like": stat_data["like"]
                    })
                    break
                elif result["code"] == -404:
                    print(f"抓取失败：{bvid}（视频不存在/已被删除）")
                    break
                elif result["code"] == -412:
                    print(f"触发限流，暂停30秒后重试，剩余重试次数：{RETRY_TIMES - retry_count - 1}")
                    retry_count += 1
                    time.sleep(30)
                else:
                    print(f"抓取失败：{bvid} | 接口报错：{result['message']}")
                    break
            except Exception as e:
                print(f"请求异常：{bvid} | 错误：{str(e)}，剩余重试次数：{RETRY_TIMES - retry_count - 1}")
                retry_count += 1
                time.sleep(5)
        time.sleep(REQUEST_INTERVAL)
    print(f"\n抓取完成！共成功抓取{len(video_list)}/{total}个视频")
    return pd.DataFrame(video_list)

# ====================== 2. 增量数据计算（和原代码完全一致，无需修改）======================
def calculate_increment(old_data: pd.Series, new_data: pd.Series) -> Dict[str, int]:
    """计算各项数据的增量"""
    keys = ["view", "danmaku", "reply", "favorite", "coin", "like"]
    return {k: max(int(new_data.get(k, 0)) - int(old_data.get(k, 0)), 0) for k in keys}

# ====================== 3. 周刊得分计算（严格匹配规则，和原代码完全一致）======================
def calculate_weekly_score(increment_data: Dict[str, int]) -> Dict[str, float]:
    view = increment_data.get("view", 0)
    danmaku = increment_data.get("danmaku", 0)
    reply = increment_data.get("reply", 0)
    favorite = increment_data.get("favorite", 0)
    coin = increment_data.get("coin", 0)
    like = increment_data.get("like", 0)


    # 基础播放得分
    base_view_score = view * 0.5 + 5000 if view > 10000 else view


    # 修正系数计算
    denominator_a = base_view_score + favorite + (danmaku + reply) * 20
    revise_a = round(((base_view_score + favorite) / denominator_a) ** 2, 2) if denominator_a else 0.00

    revise_b = 0.00
    if view and favorite:
        if favorite > coin * 2:
            revise_b = (coin ** 2 / (view * favorite)) * 1000
        else:
            revise_b = (favorite / view) * 250
        revise_b = round(min(revise_b, 50), 2)

    revise_c = 0.00
    if view and coin:
        if coin > favorite:
            revise_c = (favorite ** 2 / (view * coin)) * 250
        else:
            revise_c = (coin / view) * 250
        revise_c = round(min(revise_c, 50), 2)

    revise_d = 0.00
    if view:
        if favorite > coin:
            revise_d = (coin / view) * 25
        else:
            revise_d = (favorite / view) * 25
        revise_d = round(min(revise_d, 1), 2)


    # 各分项得分
    view_score = base_view_score * revise_d
    interact_score = (reply + danmaku) * revise_a * 15
    favorite_score = favorite * revise_b
    coin_score = coin * revise_c
    like_score = coin * 2 if like > coin * 2 else like

    # 最终得分
    final_score = view_score + interact_score + favorite_score + coin_score + like_score

    return {
        "final_score": round(final_score, 2),
        "view_score": round(view_score, 2),
        "interact_score": round(interact_score, 2),
        "favorite_score": round(favorite_score, 2),
        "coin_score": round(coin_score, 2),
        "like_score": round(like_score, 2),
        "revise_a": revise_a,
        "revise_b": revise_b,
        "revise_c": revise_c,
        "revise_d": revise_d
    }

# ====================== 4. 主程序菜单 ======================

def menu():
    print("="*50)
    print("虚拟歌手中文曲排行榜 特定视频抓取&计分工具")
    print("="*50)
    print("1. 抓取指定BV号的视频数据并保存")
    print("2. 计算增量、得分并生成排行榜")
    print("3. 退出")
    print("="*50)
    return input("请输入操作序号：")

def input_bvid_list() -> List[str]:
    print("\n请选择BV号输入模式：")
    print("1. 使用代码内预设的BV号列表")
    print("2. 手动输入BV号")
    input_mode = input("请输入模式序号：")
    if input_mode == "1":
        print(f"\n已加载预设BV号列表，共{len(DEFAULT_BVID_LIST)}个")
        return DEFAULT_BVID_LIST
    elif input_mode == "2":
        input_str = input("\n请输入要抓取的BV号，多个BV号用空格分隔：")
        bvid_list = input_str.strip().split()
        if not bvid_list:
            print("未输入有效BV号，退出程序")
            exit()
        return bvid_list
    else:
        print("无效序号，退出程序")
        exit()

def save_video_data(video_df: pd.DataFrame):
    today_str = datetime.now().strftime("%Y%m%d")
    filename = f"{today_str}_specified_video_data.csv"
    video_df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"数据已保存为：{filename}")

def calc_and_save_rank():
    old_file = input("请输入上期数据CSV文件名（如20260317_specified_video_data.csv）：")
    new_file = input("请输入本期数据CSV文件名（如20260324_specified_video_data.csv）：")
    try:
        old_df = pd.read_csv(old_file, encoding="utf-8-sig")
        new_df = pd.read_csv(new_file, encoding="utf-8-sig")
    except Exception as e:
        print(f"文件读取失败：{str(e)}，请检查文件名是否正确")
        exit()
    print("正在匹配数据，计算增量与得分...")
    rank_list = []
    common_bv = list(set(old_df["bvid"]) & set(new_df["bvid"]))
    if not common_bv:
        print("两期数据无匹配的BV号，无法计算增量")
        exit()
    total = len(common_bv)
    for idx, bvid in enumerate(common_bv, 1):
        print(f"[{idx}/{total}] 正在计算 {bvid}...")
        old_data = old_df[old_df["bvid"] == bvid].iloc[0]
        new_data = new_df[new_df["bvid"] == bvid].iloc[0]
        increment = calculate_increment(old_data, new_data)
        score_result = calculate_weekly_score(increment)
        rank_list.append({
            "排名": 0,
            "BV号": bvid,
            "标题": new_data["title"],
            "UP主": new_data["author"],
            "最终得分": score_result["final_score"],
            "周期新增播放": increment["view"],
            "周期新增弹幕": increment["danmaku"],
            "周期新增评论": increment["reply"],
            "周期新增收藏": increment["favorite"],
            "周期新增投币": increment["coin"],
            "周期新增点赞": increment["like"],
            "播放得分": score_result["view_score"],
            "互动得分": score_result["interact_score"],
            "收藏得分": score_result["favorite_score"],
            "投币得分": score_result["coin_score"],
            "点赞得分": score_result["like_score"],
            "修正A": score_result["revise_a"],
            "修正B": score_result["revise_b"],
            "修正C": score_result["revise_c"],
            "修正D": score_result["revise_d"]
        })
    rank_df = pd.DataFrame(rank_list)
    rank_df = rank_df.sort_values(by="最终得分", ascending=False).reset_index(drop=True)
    rank_df["排名"] = rank_df.index + 1
    rank_df.to_csv("specified_rank_result.csv", index=False, encoding="utf-8-sig")
    print("="*50)
    print(f"排行榜生成完成！共{len(rank_df)}条有效稿件，已保存为 specified_rank_result.csv")
    print("\n完整排名预览：")
    print(rank_df[["排名", "BV号", "标题", "UP主", "最终得分"]].to_string(index=False))

def main():
    while True:
        choice = menu()
        if choice == "1":
            bvid_list = input_bvid_list()
            video_df = get_specified_video_data(bvid_list)
            if not video_df.empty:
                save_video_data(video_df)
            else:
                print("未抓取到任何有效数据")
        elif choice == "2":
            calc_and_save_rank()
        elif choice == "3":
            print("退出程序")
            break
        else:
            print("无效序号，请重新运行程序选择")

if __name__ == "__main__":
    main()

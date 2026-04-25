import streamlit as st
import requests
import time
import pandas as pd
from datetime import datetime

# 保留原有的全局配置、get_specified_video_data、calculate_increment、calculate_weekly_score函数（完全复用）
DEFAULT_BVID_LIST = [
    "BV1LXwyzkEqo",
]
REQUEST_INTERVAL = 2
RETRY_TIMES = 3
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json, text/plain, */*"
}

# 【复用原函数】直接复制get_specified_video_data、calculate_increment、calculate_weekly_score
def get_specified_video_data(bvid_list):
    # 原函数代码（完全复制）
    pass
def calculate_increment(old_data: pd.Series, new_data: pd.Series) -> dict:
    # 原函数代码（完全复制）
    pass
def calculate_weekly_score(increment_data: dict) -> dict:
    # 原函数代码（完全复制）
    pass

# 重构交互为Web界面
st.title("虚拟歌手中文曲排行榜工具")
tab1, tab2 = st.tabs(["📥 抓取视频数据", "🏆 生成排行榜"])

with tab1:
    st.subheader("抓取指定BV号数据")
    mode = st.radio("选择BV号来源", ["使用预设列表", "手动输入"])
    bvid_list = []
    if mode == "使用预设列表":
        st.write(f"预设BV号：{DEFAULT_BVID_LIST}")
        bvid_list = DEFAULT_BVID_LIST
    else:
        input_str = st.text_input("输入BV号（多个用空格分隔）", placeholder="BV1LXwyzkEqo BVxxxxxx")
        if input_str:
            bvid_list = input_str.strip().split()
    
    if st.button("开始抓取"):
        if not bvid_list:
            st.error("请输入有效BV号！")
        else:
            with st.spinner("正在抓取数据..."):
                video_df = get_specified_video_data(bvid_list)
            if not video_df.empty:
                st.success(f"抓取成功！共{len(video_df)}个视频")
                st.dataframe(video_df)
                # 生成下载链接（适配移动端）
                today_str = datetime.now().strftime("%Y%m%d")
                csv_data = video_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="📤 下载CSV数据",
                    data=csv_data,
                    file_name=f"{today_str}_specified_video_data.csv",
                    mime="text/csv"
                )
            else:
                st.warning("未抓取到有效数据")

with tab2:
    st.subheader("计算增量并生成排行榜")
    old_file = st.file_uploader("上传上期数据CSV", type="csv")
    new_file = st.file_uploader("上传本期数据CSV", type="csv")
    
    if st.button("生成排行榜"):
        if not old_file or not new_file:
            st.error("请上传两期数据！")
        else:
            with st.spinner("正在计算增量和得分..."):
                old_df = pd.read_csv(old_file, encoding="utf-8-sig")
                new_df = pd.read_csv(new_file, encoding="utf-8-sig")
                common_bv = list(set(old_df["bvid"]) & set(new_df["bvid"]))
                if not common_bv:
                    st.error("两期数据无匹配的BV号！")
                else:
                    rank_list = []
                    for bvid in common_bv:
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
            
            st.success(f"排行榜生成完成！共{len(rank_df)}条数据")
            st.dataframe(rank_df[["排名", "BV号", "标题", "UP主", "最终得分"]])  # 预览核心列
            # 下载完整排行榜
            csv_data = rank_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button(
                label="📤 下载完整排行榜",
                data=csv_data,
                file_name="specified_rank_result.csv",
                mime="text/csv"
            )

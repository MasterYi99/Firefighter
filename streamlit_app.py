import streamlit as st
import pandas as pd
import json
import os
import logic  # 匯入您既有的核心邏輯

# 1. 設定頁面配置 (必須是第一個 Streamlit 指令)
st.set_page_config(page_title="勤務排班系統", layout="wide")

# 2. 載入人員設定檔 (與 app.py 共用邏輯)
def load_staff_config():
    config_path = "staff_config.json"
    # 預設名單 (若檔案不存在)
    default_map = {
        "許哲翊": "A", "郭獻鴻": "B", "蕭淳碩": "C", "黃仁炫": "101", "馬筠喨": "102", "許欣融": "103", "侯少穎": "104",
        "黃政偉": "105", "林戰培": "106", "張景翔": "107", "張冠傑": "108", "簡佳懿": "109", "繆昆霖": "110", "盧柏宏": "111",
        "黃建嘉": "112", "薛志中": "113", "劉又中": "114", "張文嘉": "115", "宋易潤": "116", "柯廷儒": "201", "許辰瑋": "202",
        "王雅萱": "203", "林宏叡": "204", "徐盟欽": "205", "吳致緯": "206", "張鈞寗": "207", "李芊慧": "208", "高承鈺": "209",
        "黃科諺": "210", "林冠宇": "211", "林俊吉": "212", "林忠穎": "213", "王羽萱": "214", "李旂緡": "401", "羅楷崴": "402",
        "盧建丞": "403"
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_map
    return default_map

staff_map = load_staff_config()

def save_staff_config(new_config):
    try:
        with open("staff_config.json", "w", encoding="utf-8") as f:
            json.dump(new_config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"儲存失敗: {e}")
        return False

# 新增：歷史紀錄存取功能
HISTORY_FILE = "schedule_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_to_history(date_key, schedule, night_shift, stats_data):
    history = load_history()
    history[str(date_key)] = {"schedule": schedule, "night_shift": night_shift, "stats": stats_data}
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

# 3. 側邊欄設定
with st.sidebar:
    st.title("🚒 勤務排班系統")
    app_mode = st.radio("功能選擇", ["排班執行", "歷史查詢", "人員管理"])
    st.markdown("---")
    
    if app_mode == "排班執行":
        # 檔案上傳
        uploaded_file = st.file_uploader("1. 上傳勤務表 Excel", type=["xlsx", "xls", "csv"])
        
        # 日期輸入
        target_date = st.number_input("2. 輸入今日日期 (數字)", min_value=2, max_value=31, value=20, step=1, help="系統會自動計算昨日並進行對照")
        
        # 執行按鈕
        run_btn = st.button("🚀 執行排班", type="primary", use_container_width=True)
        
        st.markdown("---")
        st.caption("說明：藍色字體為 2xx 專救人員")

# 4. 輔助函式：格式化姓名 (2xx 變藍色)
def format_names(names_input):
    """將名字列表轉為 Markdown 字串，2xx 開頭顯示為藍色"""
    if not names_input:
        return ""
    if isinstance(names_input, str):
        names_input = [names_input]
        
    formatted = []
    for name in names_input:
        # 檢查是否為 2xx 開頭 (例如 "201柯廷儒")
        if str(name).startswith("2"):
            formatted.append(f":blue[{name}]")
        else:
            formatted.append(name)
    return "、".join(formatted)

def render_day_schedule(title, schedule_data, night_shift):
    """顯示單日排班表"""
    st.subheader(title)
    
    if not schedule_data:
        st.warning("無法產生排班表 (可能無資料)")
        return

    # --- 資料轉換，將勤務種類轉為行 ---
    duty_types = ["值班", "91救護", "92救護", "11車組", "12車組"]
    time_slots = [row['slot'] for row in schedule_data]
    
    pivoted_data = {
        "值班":   [format_names(row['watch']) for row in schedule_data],
        "91救護": [format_names(row['91']) for row in schedule_data],
        "92救護": [format_names(row['92']) for row in schedule_data],
        "11車組": [format_names(row['c11']) for row in schedule_data],
        "12車組": [format_names(row['c12']) for row in schedule_data],
    }

    # --- 組合新的 Markdown 表格 ---
    # 表頭 (時段)
    md_table = f"| 勤務種類 | {' | '.join(time_slots)} |\n"
    # 分隔線
    md_table += f"|:---|{'|:'.join(['---'] * len(time_slots))}|\n"
    # 內容 (勤務)
    for duty in duty_types:
        names_by_slot = ' | '.join(pivoted_data[duty])
        md_table += f"| **{duty}** | {names_by_slot} |\n"
    
    st.markdown(md_table)
    
    # 顯示大夜名單
    if night_shift:
        st.info(f"🌙 **大夜名單**: {format_names(night_shift)}")
    else:
        st.info("🌙 **大夜名單**: 無")

# 5. 主程式邏輯
if app_mode == "人員管理":
    st.subheader("⚙️ 人員名單管理")
    st.info("可在下方表格直接編輯、新增或刪除人員，完成後請點擊「儲存設定」。")
    
    # 準備資料
    current_data = [{"姓名": k, "ID": v} for k, v in staff_map.items()]
    # 簡單排序
    current_data.sort(key=lambda x: str(x["ID"]))
    
    df_staff = pd.DataFrame(current_data)
    
    edited_df = st.data_editor(
        df_staff,
        num_rows="dynamic",
        column_config={
            "姓名": st.column_config.TextColumn("姓名", required=True),
            "ID": st.column_config.TextColumn("ID", required=True, help="1xx:隊員, 2xx:專救, 4xx:役男, A/B/C:幹部"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("💾 儲存設定"):
        new_map = {}
        for _, row in edited_df.iterrows():
            if row["姓名"] and row["ID"]:
                new_map[row["姓名"]] = str(row["ID"]).strip()
        
        if save_staff_config(new_map):
            st.success("設定已儲存！")
            st.rerun()

elif app_mode == "排班執行":
    if run_btn:
        if not uploaded_file:
            st.error("請先上傳 Excel 檔案！")
        else:
            try:
                # 讀取檔案
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file, header=2)
                else:
                    df = pd.read_excel(uploaded_file, header=2)
                df.rename(columns={df.columns[0]: '日期'}, inplace=True)

                # 計算日期
                yesterday = target_date - 1
                
                # --- 執行昨日排班 (獲取狀態與顯示用) ---
                res_prev, night_prev, _ = logic.generate_schedule(df, yesterday, staff_map)
                
                # 取得昨日休假與最後一班狀態 (為了傳遞給今日邏輯，確保連續性)
                status_prev = logic.get_staff_status(df, yesterday, staff_map)
                prev_day_off = [k for k, v in status_prev.items() if v['stat'] == 'OFF']
                
                last_watch = ""
                last_ems = []
                if res_prev:
                    last_slot = res_prev[-1]
                    last_watch = last_slot['watch']
                    last_ems = last_slot['91'] + last_slot['92']

                # --- 執行今日排班 ---
                res_curr, night_curr, staff_stats = logic.generate_schedule(
                    df, target_date, staff_map,
                    prev_night_list=night_prev,
                    prev_day_off_list=prev_day_off,
                    last_night_watch=last_watch,
                    last_night_ems=last_ems
                )

                # --- 介面顯示 (單日) ---
                render_day_schedule(f"📅 今日 ({target_date}日) 勤務表", res_curr, night_curr)
                
                # --- 顯示人員狀態與時數 ---
                st.markdown("---")
                st.subheader("📊 今日人員狀態與時數")
                
                # 取得今日所有人的狀態 (含休假)
                status_curr = logic.get_staff_status(df, target_date, staff_map)
                # 建立時數查詢表 (staff_stats 只包含上班的人)
                hours_map = {p['id_name']: p['hours'] for p in staff_stats}
                
                table_data = []
                for name, info in status_curr.items():
                    h = hours_map.get(name, 0)
                    status_str = "🟢 上班" if info['stat'] == 'ON' else "🔴 休假"
                    table_data.append({
                        "姓名": name,
                        "狀態": status_str,
                        "本日時數": h
                    })
                
                # 轉為 DataFrame 並顯示
                df_stats = pd.DataFrame(table_data).sort_values("姓名")
                st.dataframe(df_stats, use_container_width=True, hide_index=True)
                
                # --- 儲存按鈕 ---
                if st.button("💾 儲存今日勤務表"):
                    save_to_history(target_date, res_curr, night_curr, table_data)
                    st.success(f"已成功儲存 {target_date} 日的勤務表！")

            except Exception as e:
                st.error(f"執行發生錯誤: {e}")
                # st.exception(e) # 開發時可取消註解以查看詳細錯誤

elif app_mode == "歷史查詢":
    st.subheader("🗂️ 歷史勤務表查詢")
    history = load_history()
    if not history:
        st.info("目前沒有儲存的勤務表紀錄。請先在「排班執行」中產生並儲存。")
    else:
        # 日期排序 (數字大到小)
        date_options = sorted(history.keys(), key=lambda x: int(x) if x.isdigit() else x, reverse=True)
        selected_date = st.selectbox("請選擇日期", date_options)
        
        if selected_date:
            record = history[selected_date]
            render_day_schedule(f"📅 {selected_date} 日勤務表", record['schedule'], record['night_shift'])
            
            st.markdown("---")
            st.subheader("📊 當日人員狀態與時數")
            st.dataframe(pd.DataFrame(record['stats']), use_container_width=True, hide_index=True)

    else:
        # 初始畫面提示
         st.info("👈 請在左側側邊欄上傳檔案並點擊「執行排班」")

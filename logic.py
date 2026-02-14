import pandas as pd

off_symbols = ['▲', '休', '補', '超', '公', '-']

def get_staff_status(df_data, day_val, full_id_map):
    try:
        row = df_data[df_data['日期'].astype(str).str.contains(f"^{day_val}$|^0{day_val}$", na=False)]
        status_map = {}
        if row.empty: return status_map
        for col in df_data.columns[2:]:
            name = str(col).strip()
            if name in full_id_map:
                status = str(row[name].values[0]).strip()
                status_map[f"{full_id_map[name]}{name}"] = {
                    "stat": "OFF" if any(s in status for s in off_symbols) else "ON",
                    # '○' or '★' means they are on duty, but can only work day shifts (before 18:00)
                    "is_day_only": '○' in status or '★' in status
                }
        return status_map
    except: return {}

def get_staff_pool(df_data, day_val, full_id_map):
    status_map = get_staff_status(df_data, day_val, full_id_map)
    pool, bosses = [], []
    for id_name, info in status_map.items():
        if info["stat"] == "ON":
            s_id = id_name[:3].strip()
            if any(b in s_id for b in ['A', 'B', 'C']): role = "幹部"
            elif s_id.startswith('2'): role = "專救"
            elif s_id.startswith('4'): role = "役男"
            else: role = "隊員"
            # last_job: 1=值班, 2=救護, 0=其他
            p = {"id_name": id_name, "role": role, "hours": 0, "total_watch_hours": 0, "last_job": 0, "is_day_only": info["is_day_only"]}
            if role == "幹部": bosses.append(p)
            else: pool.append(p)
    return pool, bosses

def generate_schedule(df_data, target_day, full_id_map, prev_night_list=[], prev_day_off_list=[], last_night_watch="", last_night_ems=[]):
    staff_pool, boss_pool = get_staff_pool(df_data, target_day, full_id_map)
    if not staff_pool and not boss_pool: return [], [], []
    
    time_slots = ["08-12", "12-16", "16-20", "20-24", "00-04", "04-08"]
    daily_res, tonight_night_shift = [], []
    
    # 用於 08-12 隔離
    prev_watch = last_night_watch
    prev_ems = last_night_ems

    for i, slot in enumerate(time_slots):
        is_midnight = i >= 4  # 00-08
        is_after_18_shift = i >= 2 # Shifts from 16:00 onwards (16-20, 20-24, etc.)

        # Filter out staff who can only work day shifts for evening/night duties
        slot_staff_pool = staff_pool
        slot_boss_pool = boss_pool
        if is_after_18_shift:
            slot_staff_pool = [p for p in staff_pool if not p.get('is_day_only', False)]
            slot_boss_pool = [p for p in boss_pool if not p.get('is_day_only', False)]

        # --- 1. 值班指派 (最優先) ---
        watch_cands = [p for p in slot_staff_pool if p['role'] in ['隊員', '役男']]
        
        # 役男限制：00-08不得排班，且每天最多8小時
        if is_midnight:
            watch_cands = [p for p in watch_cands if p['role'] != '役男']
        else:
            watch_cands = [p for p in watch_cands if not (p['role'] == '役男' and p['total_watch_hours'] >= 8)]

        # 深夜 00-08 禁止連上（00-04 與 04-08 必須不同人）
        if i == 5: # 04-08
            prev_0004_watch = daily_res[4]['watch']
            watch_cands = [p for p in watch_cands if p['id_name'] != prev_0004_watch]

        # 勤務隔離規則 (深夜接班)
        def watch_score(p):
            score = p['hours']
            if p['role'] == '役男' and not is_midnight: score -= 200 # 役男日間最優先
            if p['last_job'] == 2: score += 1000 # 救護下班不接值班
            if i == 0 and p['id_name'] in prev_ems: score += 2000 # 跨日隔離
            return score
        
        watch_cands.sort(key=watch_score)
        watch_p = watch_cands[0] if watch_cands else None
        
        # --- 2. 救護指派 (次優先) ---
        ems_cands = [p for p in slot_staff_pool if p['role'] in ['隊員', '專救'] and p != watch_p]
        
        def ems_score(p):
            score = p['hours']
            if p['last_job'] == 1: score += 1000 # 值班下班不接救護
            if i == 0 and p['id_name'] == prev_watch: score += 2000 # 跨日隔離
            if i == 0 and p['id_name'] in prev_day_off_list: score -= 500 # 收假優先
            return score
            
        ems_cands.sort(key=ems_score)
        e91 = ems_cands[0:2]
        e92 = ems_cands[2:4]
        
        # --- 更新狀態 ---
        ems_ids = [p['id_name'] for p in (e91 + e92)]
        if watch_p:
            watch_p['hours'] += 4
            watch_p['total_watch_hours'] += 4
            watch_p['last_job'] = 1
        for p in staff_pool:
            if p['id_name'] in ems_ids:
                p['hours'] += 4
                p['last_job'] = 2
            elif p != watch_p:
                p['last_job'] = 0

        # --- 3. 車組編組 (最後) ---
        # 11車: 1個幹部 + 3個隊員 (不含役男、不含已排救護/值班的人)
        busy_ids = ems_ids + ([watch_p['id_name']] if watch_p else [])
        avail_for_11 = [p for p in slot_staff_pool if p['id_name'] not in busy_ids and p['role'] != '役男']
        
        current_boss = slot_boss_pool[i % len(slot_boss_pool)]['id_name'] if slot_boss_pool else "無幹部"
        f11 = [current_boss] + [p['id_name'] for p in avail_for_11[:3]]
        
        # 12車: 剩餘沒班的人 + 當前值班隊員 (排除役男)
        f11_ids = [name for name in f11]
        avail_for_12 = [p for p in slot_staff_pool if p['id_name'] not in busy_ids and p['id_name'] not in f11_ids and p['role'] != '役男']
        f12 = [p['id_name'] for p in avail_for_12]
        
        # 如果值班的是隊員，加入12車
        if watch_p and watch_p['role'] == '隊員':
            f12.append(watch_p['id_name'])

        # 紀錄深夜名單
        if is_midnight:
            if watch_p: tonight_night_shift.append(watch_p['id_name'])
            tonight_night_shift.extend(ems_ids)

        daily_res.append({
            "slot": slot, 
            "watch": watch_p['id_name'] if watch_p else "無人", 
            "91": [p['id_name'] for p in e91], 
            "92": [p['id_name'] for p in e92], 
            "c11": f11, 
            "c12": f12
        })
        
        prev_watch = watch_p['id_name'] if watch_p else ""
        prev_ems = ems_ids

    return daily_res, list(set(tonight_night_shift)), (staff_pool + boss_pool)

import streamlit as st
import pandas as pd
import io
import random
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 1. UI Setup & Styling ---
st.set_page_config(page_title="AI Timetable - Full System", layout="wide")
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;700&display=swap');
        body { font-family: 'Sarabun', sans-serif; }
        .stTable td, .stTable th { 
            text-align: center !important; vertical-align: middle !important;
            white-space: pre-wrap !important; font-size: 12px; height: 65px;
        }
        /* วันจันทร์-ศุกร์ สีน้ำเงิน */
        .stTable td:first-child { color: #0047AB !important; font-weight: bold; }
        .schedule-title { 
            background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #0d6efd; 
            margin-bottom: 20px; font-weight: bold; font-size: 22px; text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. Font Registration ---
@st.cache_data
def register_thai_font():
    try:
        pdfmetrics.registerFont(TTFont('ThaiFont', 'THSarabunNew.ttf'))
        pdfmetrics.registerFont(TTFont('ThaiFont-Bold', 'THSarabunNew Bold.ttf'))
        return True
    except: return False
HAS_FONT = register_thai_font()

# --- 3. Constants ---
TIMES = ["ก่อนคาบ", "08.00-09.00", "09.00-10.00", "10.00-11.00", "11.00-12.00", "12.00-13.00", 
         "13.00-14.00", "14.00-15.00", "15.00-16.00", "16.00-17.00", "17.00-18.00", "18.00-19.00", "19.00-20.00"]
PERIODS = ["", 1, 2, 3, 4, "พัก", 6, 7, 8, 9, 10, 11, 12]
DAYS_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
DAYS_MAP = {"Mon": "จันทร์", "Tue": "อังคาร", "Wed": "พุธ", "Thu": "พฤหัสบดี", "Fri": "ศุกร์"}

# --- 4. Data & Logic Functions ---
def load_data():
    files = ['teacher.csv', 'room.csv', 'student_group.csv', 'subject.csv', 'timeslot.csv', 'teach.csv', 'register.csv']
    data = {}
    try:
        for f in files:
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip()
            data[f.replace('.csv', '')] = df
        return data
    except Exception as e:
        st.error(f"Error loading files: {e}")
        return None

def scheduler_engine(data, teacher_role_map):
    results = []
    busy_t, busy_r, busy_g = set(), set(), set()
    
    # ดึงข้อมูล Timeslot ทั้งหมด (ยกเว้นคาบพัก 5)
    all_slots = data['timeslot'][(data['timeslot']['period'] <= 12) & (data['timeslot']['period'] != 5)].copy()
    
    # แยก Timeslot เป็น 2 กลุ่ม
    priority_slots = all_slots[all_slots['period'] <= 10].to_dict('records') # คาบ 1-10
    extended_slots = all_slots[all_slots['period'] > 10].to_dict('records')  # คาบ 11-12
    
    # สุ่มลำดับภายในกลุ่มเพื่อให้ตารางกระจายตัว
    random.shuffle(priority_slots)
    random.shuffle(extended_slots)
    
    # รวมลำดับการค้นหา: หาในคาบ 1-10 ก่อน ถ้าไม่ได้จริงๆ ถึงจะไป 11-12
    search_slots = priority_slots + extended_slots
    
    for _, reg in data['register'].iterrows():
        sid, gid = str(reg['subject_id']), str(reg['group_id'])
        sub_info = data['subject'][data['subject']['subject_id'] == sid].iloc[0]
        needed = int(sub_info['theory'] + sub_info['practice'])
        tid = str(data['teach'][data['teach']['subject_id'] == sid].iloc[0]['teacher_id'])
        role = str(teacher_role_map.get(tid, "")).lower()
        
        placed = 0
        # ค้นหาที่ว่างตามลำดับความสำคัญ
        for slot in search_slots:
            if placed >= needed: break
            tsid, day, period = slot['timeslot_id'], slot['day'], int(slot['period'])
            
            # เงื่อนไขเดิม: ประชุม Leader บ่ายวันอังคาร
            if role == "leader" and day == "Tue" and period == 8: continue
            
            for _, rm in data['room'].iterrows():
                rid = str(rm['room_id'])
                if (tid, tsid) not in busy_t and (rid, tsid) not in busy_r and (gid, tsid) not in busy_g:
                    results.append({
                        'group_id': gid, 'timeslot_id': tsid, 'day': day, 
                        'period': period, 'subject_id': sid, 'teacher_id': tid, 'room_id': rid
                    })
                    busy_t.add((tid, tsid))
                    busy_r.add((rid, tsid))
                    busy_g.add((gid, tsid))
                    placed += 1
                    break
    return pd.DataFrame(results)

def get_grid_display(filtered_df, teacher_map):
    grid = pd.DataFrame(index=DAYS_TH, columns=PERIODS).fillna("")
    for _, r in filtered_df.iterrows():
        t_name = teacher_map.get(str(r['teacher_id']), r['teacher_id'])
        p_val = "พัก" if r['period'] == 5 else r['period']
        # จัดรูปแบบข้อความในตาราง (รองรับสีบนหน้าเว็บ)
        cell_text = f"{r['subject_id']}\n:blue[{t_name}]\n:grey[[{r['room_id']}]]"
        grid.at[DAYS_MAP.get(r['day'], r['day']), p_val] = cell_text
    grid.loc[:, "พัก"] = "พัก"
    grid.loc[:, ""] = ""
    return grid

def create_bulk_pdf(full_res, teacher_map, group_map, room_map):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=20)
    elements = []
    f_bold = 'ThaiFont-Bold' if HAS_FONT else 'Helvetica-Bold'
    f_reg = 'ThaiFont' if HAS_FONT else 'Helvetica'
    style_h = ParagraphStyle(name='H', fontName=f_bold, fontSize=18, alignment=1)

    categories = [
        ("ตารางสอนครูผู้สอน", 'teacher_id', teacher_map),
        ("ตารางเรียนกลุ่มนักเรียน", 'group_id', group_map),
        ("ตารางการใช้ห้องเรียน", 'room_id', room_map)
    ]

    for cat_title, col_id, name_map in categories:
        for item_id, item_name in name_map.items():
            f_df = full_res[full_res[col_id] == str(item_id)]
            if f_df.empty: continue
            elements.append(Paragraph(f"{cat_title}: {item_name}", style_h))
            elements.append(Spacer(1, 10))
            
            # สร้างตารางข้อมูลดิบสำหรับ PDF (ลบ :blue และ :grey ออก)
            grid = pd.DataFrame(index=DAYS_TH, columns=PERIODS).fillna("")
            for _, r in f_df.iterrows():
                t_name = teacher_map.get(str(r['teacher_id']), r['teacher_id'])
                p_val = "พัก" if r['period'] == 5 else r['period']
                grid.at[DAYS_MAP.get(r['day'], r['day']), p_val] = f"{r['subject_id']}\n{t_name}\n[{r['room_id']}]"
            grid.loc[:, "พัก"] = "พัก"
            
            data = [["วัน/คาบ"] + [f"{p}\n{t}" for p, t in zip(PERIODS, TIMES)]]
            for day in DAYS_TH:
                data.append([day] + [str(val) for val in grid.loc[day]])
            
            table = Table(data, colWidths=[50] + [58]*13)
            table.setStyle(TableStyle([
                ('FONT', (0,0), (-1,-1), f_reg),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
            ]))
            elements.append(table)
            elements.append(PageBreak())
    doc.build(elements)
    return buf.getvalue()

# --- 5. Execution Logic ---
data_set = load_data()
if data_set:
    # เตรียมข้อมูลสำหรับแสดงผล
    t_df = data_set['teacher'].copy()
    t_df['teacher_id'] = t_df['teacher_id'].astype(str)
    cols = t_df.columns
    prefix = t_df['prefix'].fillna('') if 'prefix' in cols else ""
    fname = t_df['firstname'].fillna('') if 'firstname' in cols else ""
    lname = t_df['lastname'].fillna('') if 'lastname' in cols else ""
    t_df['full_name'] = (prefix + fname + " " + lname).str.strip() if 'firstname' in cols else t_df['teacher_id']
    
    teacher_map = dict(zip(t_df['teacher_id'], t_df['full_name']))
    group_map = dict(zip(data_set['student_group']['group_id'].astype(str), data_set['student_group']['group_name']))
    room_map = dict(zip(data_set['room']['room_id'].astype(str), data_set['room']['room_name']))

    with st.sidebar:
        st.header("🎛️ เมนูควบคุม")
        if st.button("🚀 ประมวลผลตารางใหม่", use_container_width=True):
            role_map = dict(zip(t_df['teacher_id'], t_df['role'].astype(str).str.lower() if 'role' in cols else ["teacher"]*len(t_df)))
            st.session_state.schedule_result = scheduler_engine(data_set, role_map)

        if 'schedule_result' in st.session_state:
            st.divider()
            st.subheader("📦 Export PDF ทั้งหมด")
            if HAS_FONT:
                bulk_pdf = create_bulk_pdf(st.session_state.schedule_result, teacher_map, group_map, room_map)
                st.download_button("📥 ดาวน์โหลดตารางทั้งหมด", bulk_pdf, "all_timetables.pdf", use_container_width=True)
            else: st.error("Font not found")

        st.divider()
        view_mode = st.radio("มุมมอง", ["ตามกลุ่มเรียน", "ตามครูผู้สอน", "ตามห้องเรียน"])
        map_ref = group_map if view_mode == "ตามกลุ่มเรียน" else teacher_map if view_mode == "ตามครูผู้สอน" else room_map
        selected_val = st.selectbox("เลือกรายการ", options=list(map_ref.keys()), format_func=lambda x: map_ref.get(x, x))

    if 'schedule_result' in st.session_state and selected_val:
        # --- กำหนดหัวข้อตามมุมมอง ---
        if view_mode == "ตามกลุ่มเรียน":
            prefix_title = "ตารางเรียน"
            display_name = group_map.get(selected_val, selected_val)
        elif view_mode == "ตามครูผู้สอน":
            prefix_title = "ตารางสอนครู"
            display_name = teacher_map.get(selected_val, selected_val)
        else: # ตามห้องเรียน
            prefix_title = "ตารางห้อง"
            display_name = selected_val # แสดง room_id โดยตรง

        # แสดงหัวข้อที่มีการปรับปรุง
        st.markdown(f'<div class="schedule-title">{prefix_title} : {display_name}</div>', unsafe_allow_html=True)
        
        # --- ส่วนแสดงตารางด้านล่าง (คงเดิม) ---
        col_id = 'group_id' if view_mode=="ตามกลุ่มเรียน" else 'teacher_id' if view_mode=="ตามครูผู้สอน" else 'room_id'
        f_df = st.session_state.schedule_result[st.session_state.schedule_result[col_id] == str(selected_val)]
        grid = get_grid_display(f_df, teacher_map)
        
        disp_grid = grid.copy()
        disp_grid.columns = pd.MultiIndex.from_tuples(zip(TIMES, PERIODS))
        st.table(disp_grid)

        # รายบุคคล Export
        st.download_button("Export CSV (Raw)", f_df.to_csv(index=False).encode('utf-8-sig'), "output.csv")
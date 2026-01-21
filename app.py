import streamlit as st
import pandas as pd
import io
import random
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 1. UI Setup & Centered Styling ---
st.set_page_config(page_title="AI Timetable - Final Version", layout="wide")
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;700&display=swap');
        body { font-family: 'Sarabun', sans-serif; }
        .stTable td, .stTable th { 
            text-align: center !important; 
            vertical-align: middle !important; 
            white-space: pre-wrap !important;
            font-size: 11px;
        }
        .schedule-title { 
            background: white; padding: 15px; border-radius: 10px; 
            border-left: 5px solid #0d6efd; margin-bottom: 20px; 
            font-weight: bold; font-size: 22px; text-align: center;
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

# --- 4. Logic Functions ---
def load_data():
    files = ['teacher.csv', 'room.csv', 'student_group.csv', 'subject.csv', 'timeslot.csv', 'teach.csv', 'register.csv']
    data = {}
    try:
        for f in files:
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip() # ตัดช่องว่างหัวคอลัมน์
            data[f.replace('.csv', '')] = df
        return data
    except: return None

def scheduler_engine(data, teacher_role_map):
    results = []
    busy_t, busy_r, busy_g = set(), set(), set()
    valid_slots = data['timeslot'][(data['timeslot']['period'] <= 12) & (data['timeslot']['period'] != 5)].copy()
    slots_list = valid_slots.to_dict('records')
    random.shuffle(slots_list)
    
    for _, reg in data['register'].iterrows():
        sid, gid = str(reg['subject_id']), str(reg['group_id'])
        sub_info = data['subject'][data['subject']['subject_id'] == sid].iloc[0]
        needed = int(sub_info['theory'] + sub_info['practice'])
        tid = str(data['teach'][data['teach']['subject_id'] == sid].iloc[0]['teacher_id'])
        role = str(teacher_role_map.get(tid, "")).lower()
        
        placed = 0
        for slot in slots_list:
            if placed >= needed: break
            tsid, day, period = slot['timeslot_id'], slot['day'], int(slot['period'])
            if role == "leader" and day == "Tue" and period == 8: continue
            for _, rm in data['room'].iterrows():
                rid = str(rm['room_id'])
                if (tid, tsid) not in busy_t and (rid, tsid) not in busy_r and (gid, tsid) not in busy_g:
                    results.append({'group_id': gid, 'timeslot_id': tsid, 'day': day, 'period': period, 'subject_id': sid, 'teacher_id': tid, 'room_id': rid})
                    busy_t.add((tid, tsid)); busy_r.add((rid, tsid)); busy_g.add((gid, tsid))
                    placed += 1; break
    return pd.DataFrame(results)

def create_pdf(df_grid, title):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), topMargin=20)
    elements = []
    f_bold = 'ThaiFont-Bold' if HAS_FONT else 'Helvetica-Bold'
    f_reg = 'ThaiFont' if HAS_FONT else 'Helvetica'
    elements.append(Paragraph(f"ตารางสอน: {title}", ParagraphStyle(name='T', fontName=f_bold, fontSize=18, alignment=1)))
    elements.append(Spacer(1, 12))
    header = ["วัน/คาบ"] + [f"{p}\n{t}" for p, t in zip(PERIODS, TIMES)]
    data = [header]
    for day in DAYS_TH:
        data.append([day] + [str(val) for val in df_grid.loc[day]])
    table = Table(data, colWidths=[50] + [58]*13)
    table.setStyle(TableStyle([('FONT', (0,0), (-1,-1), f_reg), ('GRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('FONTSIZE', (0,0), (-1,-1), 8)]))
    elements.append(table)
    doc.build(elements)
    return buf.getvalue()

# --- 5. Main Execution ---
data_set = load_data()
if data_set:
    t_df = data_set['teacher'].copy()
    t_df['teacher_id'] = t_df['teacher_id'].astype(str)
    
    # --- แก้ไข KeyError: 'prefix' แบบ Robust ---
    cols = t_df.columns
    # ตรวจเช็คคอลัมน์ทีละขั้น
    prefix = t_df['prefix'].fillna('') if 'prefix' in cols else ""
    fname = t_df['firstname'].fillna('') if 'firstname' in cols else t_df['teacher_id']
    lname = t_df['lastname'].fillna('') if 'lastname' in cols else ""
    
    # สร้าง full_name โดยพิจารณาจากที่มีอยู่
    if 'firstname' in cols:
        t_df['full_name'] = (prefix + fname + " " + lname).str.strip()
    else:
        t_df['full_name'] = t_df['teacher_id']

    teacher_map = dict(zip(t_df['teacher_id'], t_df['full_name']))
    teacher_role_map = dict(zip(t_df['teacher_id'], t_df['role'].astype(str).str.lower() if 'role' in cols else ["teacher"]*len(t_df)))
    
    room_map = dict(zip(data_set['room']['room_id'].astype(str), data_set['room']['room_name']))
    group_map = dict(zip(data_set['student_group']['group_id'].astype(str), data_set['student_group']['group_name']))

    with st.sidebar:
        st.header("🎛️ เมนูควบคุม")
        view_mode = st.radio("มุมมอง", ["ตามกลุ่มเรียน", "ตามครูผู้สอน", "ตามห้องเรียน"])
        map_ref = group_map if view_mode == "ตามกลุ่มเรียน" else teacher_map if view_mode == "ตามครูผู้สอน" else room_map
        selected_val = st.selectbox("เลือกรายการ", options=list(map_ref.keys()), format_func=lambda x: map_ref.get(x, x))
        
        if st.button("🚀 ประมวลผลใหม่", use_container_width=True):
            st.session_state.schedule_result = scheduler_engine(data_set, teacher_role_map)

    if 'schedule_result' in st.session_state and selected_val:
        res_df = st.session_state.schedule_result
        col_id = 'group_id' if view_mode=="ตามกลุ่มเรียน" else 'teacher_id' if view_mode=="ตามครูผู้สอน" else 'room_id'
        f_df = res_df[res_df[col_id] == str(selected_val)].copy()
        display_name = map_ref.get(selected_val, selected_val)

        st.markdown(f'<div class="schedule-title">ตารางสอน : {display_name}</div>', unsafe_allow_html=True)
        
        # Grid สำหรับหน้าเว็บ
        grid = pd.DataFrame(index=DAYS_TH, columns=PERIODS).fillna("")
        for _, r in f_df.iterrows():
            t_name = teacher_map.get(str(r['teacher_id']), r['teacher_id'])
            rm_name = room_map.get(str(r['room_id']), r['room_id'])
            p_val = "พัก" if r['period'] == 5 else r['period']
            grid.at[DAYS_MAP.get(r['day'], r['day']), p_val] = f"{r['subject_id']}\n{t_name}\n{rm_name}"
        
        grid.loc[:, "พัก"] = "พัก"
        if view_mode == "ตามครูผู้สอน" and teacher_role_map.get(str(selected_val)) == "leader":
            grid.at["อังคาร", 8] = "ประชุม\nLeader"

        display_grid = grid.copy()
        display_grid.columns = pd.MultiIndex.from_tuples(zip(TIMES, PERIODS))
        st.table(display_grid)

        # --- 📥 ส่วนของปุ่ม Export ---
        st.divider()
        st.subheader("📥 ดาวน์โหลดข้อมูล")
        c1, c2, c3 = st.columns(3)
        
        with c1:
            # ปรับปรุง: Export CSV ในรูปแบบ Raw Data (บรรทัดต่อบรรทัด)
            csv_cols = ['group_id', 'timeslot_id', 'day', 'period', 'subject_id', 'teacher_id', 'room_id']
            # ตรวจเช็คว่า f_df มีคอลัมน์ครบไหมก่อน export
            if all(col in f_df.columns for col in csv_cols):
                csv_raw = f_df[csv_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button("Export as CSV (Raw)", csv_raw, "output.csv", "text/csv", use_container_width=True)
        
        with c2:
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    grid.to_excel(writer, sheet_name='Timetable')
                st.download_button("Export as Excel (Grid)", output.getvalue(), "output.xlsx", use_container_width=True)
            except:
                st.warning("โปรดติดตั้ง xlsxwriter")
            
        with c3:
            if HAS_FONT:
                pdf_bytes = create_pdf(grid, display_name)
                st.download_button("Export as PDF (Grid)", pdf_bytes, "output.pdf", "application/pdf", use_container_width=True)
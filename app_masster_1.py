import streamlit as st
import pandas as pd
import io
import random
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- 1. UI Setup & Styling ---
st.set_page_config(page_title="AI Timetable Admin (12 Periods)", layout="wide")
st.markdown("""
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@400;700&display=swap');
        body { font-family: 'Sarabun', sans-serif; background-color: #f4f7f6; }
        .stTable { border-radius: 10px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.1); background: white; }
        thead tr:nth-child(1) th { background-color: #0d6efd !important; color: white !important; font-size: 12px; }
        thead tr:nth-child(2) th { background-color: #e7f1ff !important; color: #0d6efd !important; font-size: 10px; }
        td { white-space: pre-wrap !important; text-align: center !important; vertical-align: middle !important; font-size: 10px; line-height: 1.2; border: 1px solid #dee2e6; }
        .schedule-title { background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #198754; margin-bottom: 20px; font-weight: bold; font-size: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. Registration of Thai Font ---
@st.cache_data
def register_thai_font():
    try:
        pdfmetrics.registerFont(TTFont('ThaiFont', 'THSarabunNew.ttf'))
        pdfmetrics.registerFont(TTFont('ThaiFont-Bold', 'THSarabunNew Bold.ttf'))
        return True
    except: return False

HAS_FONT = register_thai_font()

# --- 3. Constants (เพิ่มคาบ 11-12) ---
TIMES = ["ก่อนคาบ", "08.00-09.00", "09.00-10.00", "10.00-11.00", "11.00-12.00", "12.00-13.00", 
         "13.00-14.00", "14.00-15.00", "15.00-16.00", "16.00-17.00", "17.00-18.00", "18.00-19.00", "19.00-20.00"]
PERIODS = ["", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
DAYS_TH = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์"]
DAYS_MAP = {"Mon": "จันทร์", "Tue": "อังคาร", "Wed": "พุธ", "Thu": "พฤหัสบดี", "Fri": "ศุกร์"}

# --- 4. Core Logic Functions ---
def load_data():
    files = ['teacher.csv', 'room.csv', 'student_group.csv', 'subject.csv', 'timeslot.csv', 'teach.csv', 'register.csv']
    data = {}
    try:
        for f in files: data[f.replace('.csv', '')] = pd.read_csv(f)
        return data
    except Exception as e:
        st.error(f"❌ ไม่พบไฟล์ข้อมูล: {e}"); return None

def scheduler_engine(data):
    results = []
    busy_t, busy_r, busy_g = set(), set(), set()
    # ปรับเงื่อนไขให้รองรับถึงคาบที่ 12
    valid_slots = data['timeslot'][(data['timeslot']['period'] <= 12) & (data['timeslot']['period'] != 5)].copy()
    slots_list = valid_slots.to_dict('records')
    random.shuffle(slots_list)
    
    for _, reg in data['register'].iterrows():
        sid, gid = str(reg['subject_id']), str(reg['group_id'])
        sub_info = data['subject'][data['subject']['subject_id'] == sid].iloc[0]
        needed = int(sub_info['theory'] + sub_info['practice'])
        tid = str(data['teach'][data['teach']['subject_id'] == sid].iloc[0]['teacher_id'])
        
        placed = 0
        for slot in slots_list:
            if placed >= needed: break
            tsid = slot['timeslot_id']
            for _, rm in data['room'].iterrows():
                rid = str(rm['room_id'])
                if (tid, tsid) not in busy_t and (rid, tsid) not in busy_r and (gid, tsid) not in busy_g:
                    results.append({'group_id': gid, 'timeslot_id': tsid, 'day': slot['day'], 'period': int(slot['period']), 'subject_id': sid, 'teacher_id': tid, 'room_id': rid})
                    busy_t.add((tid, tsid)); busy_r.add((rid, tsid)); busy_g.add((gid, tsid))
                    placed += 1; break
    return pd.DataFrame(results)

def generate_pdf(grid_df, title_text):
    buffer = io.BytesIO()
    # ปรับขอบกระดาษให้เล็กลงที่สุด (20 -> 15) เพื่อเพิ่มพื้นที่
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    elements = []
    f_name = 'ThaiFont' if HAS_FONT else 'Helvetica'
    f_name_bold = 'ThaiFont-Bold' if HAS_FONT else 'Helvetica-Bold'
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('ThaiTitle', fontName=f_name_bold, fontSize=16, alignment=1, spaceAfter=10)
    elements.append(Paragraph(title_text, title_style))
    
    pdf_data = [["วัน / เวลา"] + TIMES, [""] + [str(p) for p in PERIODS]]
    for day in DAYS_TH:
        row = [day]
        for p in PERIODS:
            try:
                val = grid_df.loc[day, (slice(None), p)].values[0]
                row.append(val)
            except: row.append("-")
        pdf_data.append(row)
        
    # ปรับความกว้างคอลัมน์ใหม่สำหรับ 13 คอลัมน์ (60 คือความกว้างโดยเฉลี่ย)
    table = Table(pdf_data, colWidths=[60, 55] + [58]*12)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), f_name),
        ('BACKGROUND', (1, 0), (-1, 0), colors.blue),
        ('TEXTCOLOR', (1, 0), (-1, 0), colors.whitesmoke),
        ('BACKGROUND', (1, 1), (-1, 1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, 1), 8), ('FONTSIZE', (0, 2), (-1, -1), 7),
    ]))
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()

# --- 5. Main Execution ---
data_set = load_data()
if data_set:
    g_df = data_set['student_group']
    group_map = dict(zip(g_df['group_id'].astype(str), g_df['group_name'] if 'group_name' in g_df.columns else g_df['group_id']))
    t_df = data_set['teacher']
    t_names = t_df['prefix'] + t_df['firstname'] if ('prefix' in t_df.columns and 'firstname' in t_df.columns) else t_df['teacher_id']
    teacher_map = dict(zip(t_df['teacher_id'].astype(str), t_names))
    r_df = data_set['room']
    room_map = dict(zip(r_df['room_id'].astype(str), r_df['room_name'] if 'room_name' in r_df.columns else r_df['room_id']))

    with st.sidebar:
        st.header("🎛️ เมนูควบคุม")
        view_mode = st.radio("เลือกมุมมองตาราง", ["ตามกลุ่มเรียน", "ตามครูผู้สอน", "ตามห้องเรียน"])
        map_ref = group_map if view_mode == "ตามกลุ่มเรียน" else teacher_map if view_mode == "ตามครูผู้สอน" else room_map
        selected_val = st.selectbox(f"เลือก{view_mode[4:]}", options=list(map_ref.keys()), format_func=lambda x: map_ref.get(x, x))
        display_name = map_ref.get(selected_val, selected_val)
        
        if st.button("🚀 ประมวลผลตารางใหม่", use_container_width=True):
            st.session_state.schedule_result = scheduler_engine(data_set)

    if 'schedule_result' in st.session_state:
        res_df = st.session_state.schedule_result
        col_name = 'group_id' if view_mode=="ตามกลุ่มเรียน" else 'teacher_id' if view_mode=="ตามครูผู้สอน" else 'room_id'
        f_df = res_df[res_df[col_name] == str(selected_val)]

        full_title = f"{'ตารางเรียนกลุ่ม :' if view_mode=='ตามกลุ่มเรียน' else 'ตารางสอนครู :' if view_mode=='ตามครูผู้สอน' else 'ตารางห้อง :'} {display_name}"
        st.markdown(f'<div class="schedule-title">{full_title}</div>', unsafe_allow_html=True)
        
        grid = pd.DataFrame(index=DAYS_TH, columns=PERIODS).fillna("-")
        for _, r in f_df.iterrows():
            grid.at[DAYS_MAP.get(r['day'], r['day']), r['period']] = f"{r['subject_id']}\n{r['teacher_id']}\n{r['room_id']}"
            
        grid.loc[:, 5] = "พัก"
        grid.loc[:, ""] = "กิจกรรม\nหน้าเสาธง"
        
        grid.columns = pd.MultiIndex.from_tuples(zip(TIMES, PERIODS))
        st.table(grid)
        
        st.markdown("### 📥 ส่งออก")
        c1, c2 = st.columns(2)
        with c1: st.download_button("💾 Download All CSV", res_df.to_csv(index=False).encode('utf-8-sig'), "all_schedule.csv", use_container_width=True)
        with c2: st.download_button("📄 Download PDF (View)", generate_pdf(grid, full_title), f"Schedule_{display_name}.pdf", use_container_width=True)
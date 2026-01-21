import pandas as pd

# 1. โหลดข้อมูล
df = pd.read_csv('subject.csv')
df.columns = df.columns.str.strip()

# 2. คำนวณ theory + practice ของทุกแถว แล้วหาผลรวมทั้งหมด (Grand Total)
total_hours_all_subjects = (df['theory'].fillna(0) + df['practice'].fillna(0)).sum()

print(f"จำนวนชั่วโมงรวมทุกรายวิชาในไฟล์: {total_hours_all_subjects} ชั่วโมง")
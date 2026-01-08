import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

st.set_page_config(page_title="كاشف التكلفة", layout="wide")

# الحماية
if "password" not in st.session_state: st.session_state["password"] = ""
if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒"); password = st.text_input("Password", type="password")
    if password == st.secrets["PASSWORD"]: st.session_state["password"] = password; st.rerun()
    else: st.stop()

def load_debug_data(file_header, file_items):
    try:
        tree_h = ET.parse(file_header); df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        tree_i = ET.parse(file_items); df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # 1. فلترة وتجهيز الفواتير (مبيعات ومرتجع فقط)
        if 'IsDelete' in df_header.columns: df_header = df_header[~df_header['IsDelete'].isin(['True', '1'])]
        
        # اختيار الفواتير (نفس الفلتر السابق الناجح)
        sales_vouchers = [v for v in df_header['VoucherName'].unique() if v and ('Sale' in v or 'Cash' in v or 'Invoice' in v or 'Return' in v or 'مرتجع' in v)]
        valid_transcodes = df_header[df_header['VoucherName'].isin(sales_vouchers)]['TransCode'].tolist()
        
        # فلترة الأصناف بناء على الفواتير المختارة
        df_items = df_items[df_items['TransCode'].isin(valid_transcodes)]
        
        # تجهيز الكمية
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        
        return df_items
    except Exception as e: st.error(str(e)); return None

st.title("🕵️‍♂️ كاشف التكلفة المفقودة")
st.info("نبحث عن عمود يعطينا مجموع يقارب: 1,079,724 (تكلفة البضاعة المباعة)")

f1 = st.file_uploader("ملف الفواتير (InvoiceDetails)", type='xml')
f2 = st.file_uploader("ملف الأصناف (RowItems)", type='xml')

if f1 and f2:
    df = load_debug_data(f1, f2)
    if df is not None:
        st.write(f"عدد الأصناف التي يتم تحليلها: {len(df)}")
        
        results = []
        # نفحص كل الأعمدة الموجودة في الملف
        for col in df.columns:
            # نتجاهل الأعمدة النصية ونركز على الأرقام المحتملة
            try:
                # تحويل العمود لرقم
                numeric_col = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                # تخطي الأعمدة الصفرية أو الصغيرة جداً
                if numeric_col.sum() == 0: continue
                
                # المعادلة: المجموع = الكمية * قيمة العمود
                total_value = (df['Qty'] * numeric_col).sum()
                
                # نحفظ النتيجة
                results.append({'Column Name': col, 'Total Value (Cost)': total_value})
            except:
                continue
                
        # عرض النتائج مرتبة
        res_df = pd.DataFrame(results).sort_values('Total Value (Cost)', ascending=False)
        
        # تنسيق الرقم ليظهر بالفواصل
        st.dataframe(res_df.style.format({'Total Value (Cost)': '{:,.2f}'}), use_container_width=True)

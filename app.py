import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

st.set_page_config(page_title="كاشف التكلفة 2.0", layout="wide")

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
        
        # فلترة الفواتير (مبيعات ومرتجع فقط)
        if 'IsDelete' in df_header.columns: df_header = df_header[~df_header['IsDelete'].isin(['True', '1'])]
        sales_vouchers = [v for v in df_header['VoucherName'].unique() if v and ('Sale' in v or 'Cash' in v or 'Invoice' in v or 'Return' in v or 'مرتجع' in v)]
        valid_transcodes = df_header[df_header['VoucherName'].isin(sales_vouchers)]['TransCode'].tolist()
        df_items = df_items[df_items['TransCode'].isin(valid_transcodes)]
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        
        return df_items
    except Exception as e: st.error(str(e)); return None

st.title("🕵️‍♂️ كاشف التكلفة (المسح المزدوج)")
st.info("نبحث عن الرقم: 1,008,451 (الإجمالي) أو 921,704 (الصافي)")

# أسماء الأزرار واضحة الآن 😉
f1 = st.file_uploader("ارفع ملف StockInvoiceDetails.xml", type='xml')
f2 = st.file_uploader("ارفع ملف StockInvoiceRowItems.xml", type='xml')

if f1 and f2:
    df = load_debug_data(f1, f2)
    if df is not None:
        results = []
        for col in df.columns:
            try:
                numeric_col = pd.to_numeric(df[col], errors='coerce').fillna(0)
                if numeric_col.sum() == 0: continue
                
                # الاحتمال الأول: العمود هو التكلفة الإجمالية (بدون ضرب)
                sum_direct = numeric_col.sum()
                
                # الاحتمال الثاني: العمود هو سعر الحبة (مع ضرب في الكمية)
                sum_multiplied = (df['Qty'] * numeric_col).sum()
                
                results.append({
                    'اسم العمود': col,
                    'المجموع (كمبلغ إجمالي)': sum_direct,
                    'المجموع (كسعر حبة)': sum_multiplied
                })
            except: continue
                
        res_df = pd.DataFrame(results)
        # تنسيق الأرقام
        st.dataframe(res_df.style.format({'المجموع (كمبلغ إجمالي)': '{:,.2f}', 'المجموع (كسعر حبة)': '{:,.2f}'}), use_container_width=True)

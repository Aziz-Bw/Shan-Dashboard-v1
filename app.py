import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET

st.set_page_config(layout="wide", page_title="فحص ملفات النظام")

# --- 🔐 نظام الحماية (موجود لضمان الخصوصية) ---
if "password" not in st.session_state:
    st.session_state["password"] = ""

if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 تسجيل الدخول")
    password = st.text_input("كلمة المرور", type="password")
    if password == st.secrets["PASSWORD"]:
        st.session_state["password"] = password
        st.rerun()
    else:
        st.stop()

# --- 🕵️‍♂️ المحقق كونان (كشف الأعمدة) ---
def parse_xml_debug(uploaded_file):
    try:
        tree = ET.parse(uploaded_file)
        root = tree.getroot()
        all_records = []
        # نقرأ 3 صفوف فقط عشان السرعة
        for i, child in enumerate(root):
            if i > 3: break 
            record = {}
            for subchild in child:
                record[subchild.tag] = subchild.text
            all_records.append(record)
        return pd.DataFrame(all_records)
    except Exception as e:
        st.error(f"Error: {e}")
        return None

st.title("🕵️‍♂️ وضع الفحص: كشف أسماء الأعمدة الحقيقية")
st.info("الهدف من هذه الشاشة معرفة المسميات البرمجية داخل ملفاتك لتصميم الداشبورد بدقة.")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. ملف الفواتير (InvoiceDetails)")
    file1 = st.file_uploader("ارفع ملف StockInvoiceDetails.xml", type=['xml'], key="f1")
    if file1:
        df1 = parse_xml_debug(file1)
        if df1 is not None:
            st.success("✅ تم قراءة الأعمدة:")
            st.code(list(df1.columns)) # هذا هو الكنز الذي نبحث عنه
            st.write("عينة بيانات:")
            st.dataframe(df1.head(2))

with col2:
    st.subheader("2. ملف الأصناف (RowItems)")
    file2 = st.file_uploader("ارفع ملف StockInvoiceRowItems.xml", type=['xml'], key="f2")
    if file2:
        df2 = parse_xml_debug(file2)
        if df2 is not None:
            st.success("✅ تم قراءة الأعمدة:")
            st.code(list(df2.columns))
            st.write("عينة بيانات:")
            st.dataframe(df2.head(2))

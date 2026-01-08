import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import xml.etree.ElementTree as ET

# --- 1. إعداد الصفحة والتصميم ---
st.set_page_config(page_title="مدير قطع الغيار الذكي", layout="wide", page_icon="⚙️")

# تصميم CSS لتحسين مظهر الأرقام
st.markdown("""
<style>
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #0068c9;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. نظام الحماية ---
if "password" not in st.session_state:
    st.session_state["password"] = ""

if st.session_state["password"] != st.secrets["PASSWORD"]:
    st.title("🔒 تسجيل الدخول")
    password = st.text_input("أدخل كلمة المرور للمتابعة", type="password")
    if password == st.secrets["PASSWORD"]:
        st.session_state["password"] = password
        st.rerun()
    else:
        st.stop()

# --- 3. دالة المعالجة الذكية ---
@st.cache_data(ttl=3600)
def load_data(file_header, file_items):
    try:
        # قراءة ملف الفواتير
        tree_h = ET.parse(file_header)
        df_header = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_h.getroot()])
        
        # قراءة ملف الأصناف
        tree_i = ET.parse(file_items)
        df_items = pd.DataFrame([{child.tag: child.text for child in row} for row in tree_i.getroot()])
        
        # --- تنظيف البيانات ---
        
        # 1. إصلاح التاريخ (الحل السحري باستخدام TransDateValue)
        # الرقم 45538 هو نظام إكسل، يبدأ العد من 30-12-1899
        df_header['Date'] = pd.to_datetime(
            pd.to_numeric(df_header['TransDateValue'], errors='coerce'), 
            unit='D', 
            origin='1899-12-30'
        )
        
        # تنظيف الأرقام
        df_header['GrandTotal'] = pd.to_numeric(df_header['InvoiceTotal'], errors='coerce').fillna(0)
        df_header['TaxTotal'] = pd.to_numeric(df_header['taxtotal'], errors='coerce').fillna(0)
        
        # 2. تنظيف الأصناف
        df_items['Qty'] = pd.to_numeric(df_items['TotalQty'], errors='coerce').fillna(0)
        df_items['Amount'] = pd.to_numeric(df_items['netStockAmount'], errors='coerce').fillna(0)
        df_items['Cost'] = pd.to_numeric(df_items['CostFactor'], errors='coerce').fillna(0)
        
        # حساب الربح
        df_items['Profit'] = df_items['Amount'] - (df_items['Cost'] * df_items['Qty'])

        # 3. الدمج
        full_data = pd.merge(
            df_items, 
            df_header[['TransCode', 'Date', 'LedgerName', 'InvoiceNo', 'SalesMan']], 
            on='TransCode', 
            how='inner' # نستخدم inner لنضمن أن كل صنف له فاتورة وتاريخ
        )
        
        # حذف أي صفوف ليس لها تاريخ صحيح
        full_data = full_data.dropna(subset=['Date'])
        
        return full_data
        
    except Exception as e:
        st.error(f"حدث خطأ في

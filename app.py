import streamlit as st
import pandas as pd
import plotly.express as px
import xml.etree.ElementTree as ET

# إعداد الصفحة
st.set_page_config(page_title="لوحة تحكم قطع الغيار", layout="wide", page_icon="🔒")

# --- 🔐 نظام الحماية (نقطة التفتيش) ---
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # حذف كلمة المرور من الذاكرة للأمان
        else:
            st.session_state["password_correct"] = False

    # إذا تم تسجيل الدخول مسبقاً
    if st.session_state.get("password_correct", False):
        return True

    # واجهة تسجيل الدخول
    st.title("🔒 تسجيل الدخول محمي")
    st.text_input(
        "يرجى إدخال كلمة المرور", type="password", on_change=password_entered, key="password"
    )
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("⛔ كلمة المرور غير صحيحة")

    return False

# إذا لم ينجح في كلمة المرور، أوقف البرنامج هنا
if not check_password():
    st.stop()

# -------------------------------------------------------------------
# 👇 هنا يبدأ برنامجك الأصلي (لن يظهر إلا بعد كلمة المرور)
# -------------------------------------------------------------------

# دالة قراءة XML
def parse_xml_to_df(uploaded_file):
    try:
        tree = ET.parse(uploaded_file)
        root = tree.getroot()
        all_records = []
        for child in root:
            record = {}
            for subchild in child:
                record[subchild.tag] = subchild.text
            all_records.append(record)
        return pd.DataFrame(all_records)
    except Exception as e:
        st.error(f"خطأ: {e}")
        return None

# الواجهة الرئيسية
st.title("🔧 لوحة القيادة: إدارة قطع الغيار")
st.markdown("---")

with st.sidebar:
    st.header("📂 رفع البيانات")
    st.success("✅ تم تسجيل الدخول بنجاح")
    file_details = st.file_uploader("ملف الفواتير (StockInvoiceDetails)", type=['xml'])
    file_items = st.file_uploader("ملف الأصناف (StockInvoiceRowItems)", type=['xml'])

if file_details and file_items:
    df_header = parse_xml_to_df(file_details)
    df_items = parse_xml_to_df(file_items)
    
    if df_header is not None:
        # معالجة البيانات
        cols_num = ['Net', 'Tax', 'Total']
        for c in cols_num:
            if c in df_header.columns:
                df_header[c] = pd.to_numeric(df_header[c], errors='coerce').fillna(0)
        
        # العرض
        total_sales = df_header['Net'].sum() if 'Net' in df_header.columns else 0
        st.metric("إجمالي المبيعات", f"{total_sales:,.0f} ر.س")
        
        if 'Salesman' in df_header.columns:
            st.subheader("مبيعات البائعين")
            fig = px.bar(df_header.groupby('Salesman')['Net'].sum().reset_index(), x='Salesman', y='Net')
            st.plotly_chart(fig, use_container_width=True)
        
        st.success("تم تحليل البيانات بنجاح!")
else:
    st.info("👈 يرجى رفع ملفات XML من القائمة الجانبية لبدء التحليل.")

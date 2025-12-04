import streamlit as st
from dashscope import MultiModalConversation, Generation
from dashscope.audio.tts import SpeechSynthesizer
import dashscope
from PIL import Image, ImageDraw, ImageFont
import tempfile
import os
import qrcode
import io
import requests
import docx
from docx.shared import Pt, RGBColor
import PyPDF2

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="小学语文作文批改宝",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed" # 默认收起侧边栏，让主界面更清爽
)

# --- 🎨 深度美化：自定义 CSS ---
st.markdown("""
    <style>
    /* 全局背景色：极淡的暖米色，护眼 */
    .stApp {
        background-color: #FFFBF0;
    }
    
    /* 隐藏默认菜单 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 标题样式 */
    h1 {
        color: #E67E22;
        font-weight: 800;
        text-align: center;
        font-family: "Microsoft YaHei", sans-serif;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 选项卡 (Tabs) 美化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
        border-radius: 20px;
        padding: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 15px;
        color: #666;
        font-weight: bold;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #eee;
        flex: 1; /* 让两个标签平分宽度 */
    }
    .stTabs [aria-selected="true"] {
        background-color: #FF9F43 !important;
        color: white !important;
        border: none;
        box-shadow: 0 4px 10px rgba(255, 159, 67, 0.4);
    }
    
    /* 上传框美化 */
    div[data-testid="stFileUploader"] {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        border: 2px dashed #FFD180; /* 虚线边框变橙色 */
        text-align: center;
    }
    div[data-testid="stFileUploader"] section {
        background-color: #fff;
    }
    
    /* 按钮美化：大圆角橙色按钮 */
    .stButton>button {
        width: 100%;
        border-radius: 30px;
        height: 55px;
        font-size: 18px !important;
        font-weight: bold;
        border: none;
        background: linear-gradient(135deg, #FFB74D 0%, #FF9800 100%);
        color: white;
        box-shadow: 0 6px 15px rgba(255, 152, 0, 0.3);
        margin-top: 10px;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        color: white !important;
    }
    
    /* 文本框美化 */
    .stTextArea textarea {
        background-color: #ffffff;
        border: 2px solid #FFE0B2;
        border-radius: 15px;
        padding: 15px;
        font-size: 16px;
        color: #333;
    }
    
    /* 结果卡片 */
    div.css-card {
        background-color: white;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border-top: 5px solid #FF9F43;
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 基础配置 ---
api_key = st.secrets.get("DASHSCOPE_API_KEY")
if not api_key:
    st.error("⚠️ 请配置 API Key")
    st.stop()
dashscope.api_key = api_key

if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = ""
if 'review_result' not in st.session_state:
    st.session_state.review_result = ""

# --- 🛠️ 工具函数 (保持不变) ---
def compress_image(image, max_width=1024):
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    return image

def generate_audio_dashscope(text, voice_name):
    voice_map = {
        "👩‍🏫 温柔女老师 (知厨)": "sambert-zhichu-v1",
        "👨‍🏫 阳光男老师 (知达)": "sambert-zhida-v1"
    }
    model_id = voice_map.get(voice_name, "sambert-zhichu-v1")
    try:
        text = text.replace("**", "").replace("###", "").replace("---", "")
        if len(text) > 800: text = text[:800]
        result = SpeechSynthesizer.call(model=model_id, text=text, sample_rate=48000)
        if result.get_audio_data() is not None:
            with open("review.mp3", "wb") as f:
                f.write(result.get_audio_data())
            return True
        return False
    except Exception as e:
        st.warning(f"语音服务繁忙: {e}")
        return False

@st.cache_resource
def get_font():
    font_path = "SimHei.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(font_path, "wb") as f:
                    f.write(r.content)
        except: return None 
    return font_path

def create_word_report(text):
    doc = docx.Document()
    title = doc.add_heading('🏆 小学语文作文批改报告', 0)
    title.alignment = 1
    lines = text.split('\n')
    for line in lines:
        clean_line = line.strip()
        if not clean_line: continue
        if clean_line.startswith('###'):
            doc.add_heading(clean_line.replace('#', '').strip(), level=2)
        elif clean_line.startswith('**') and clean_line.endswith('**'):
            p = doc.add_paragraph()
            run = p.add_run(clean_line.replace('*', ''))
            run.bold = True
        else:
            doc.add_paragraph(clean_line)
    doc.add_paragraph('\nGenerated by 小学语文作文批改宝 (AI)').alignment = 2
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f

def create_review_card(text):
    font_path = get_font()
    try:
        title_font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
        content_font = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        content_font = ImageFont.load_default()

    chars_per_line = 32
    line_height = 35
    margin = 40
    header_height = 120
    footer_height = 80
    
    display_lines = []
    paragraphs = text.split('\n')
    for para in paragraphs:
        clean_line = para.replace('#', '').replace('*', '')
        if not clean_line.strip():
            display_lines.append("")
            continue
        for i in range(0, len(clean_line), chars_per_line):
            display_lines.append(clean_line[i:i+chars_per_line])
    
    total_content_height = len(display_lines) * line_height
    img_height = header_height + total_content_height + footer_height
    img_width = 800

    img = Image.new('RGB', (img_width, img_height), color=(255, 255, 245))
    draw = ImageDraw.Draw(img)

    draw.text((40, 40), "🏆 作文批改报告", fill=(255, 75, 75), font=title_font)
    draw.line((40, 100, 760, 100), fill=(200, 200, 200), width=2)
    
    y_text = header_height
    for line in display_lines:
        draw.text((margin, y_text), line, fill=(50, 50, 50), font=content_font)
        y_text += line_height
        
    draw.text((margin, img_height - 50), "🤖 小学语文作文批改宝", fill=(150, 150, 150), font=content_font)
    return img

def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])
def read_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages: text += page.extract_text() + "\n"
    return text
def stitch_images(image_list):
    if not image_list: return None
    images = [Image.open(x) for x in image_list]
    widths, heights = zip(*(i.size for i in images))
    new_im = Image.new('RGB', (max(widths), sum(heights)), (255, 255, 255))
    y_offset = 0
    for im in images: new_im.paste(im, (0, y_offset)); y_offset += im.size[1]
    return compress_image(new_im)

# --- 3. 侧边栏 (仅保留设置) ---
with st.sidebar:
    st.header("⚙️ 设置")
    grade = st.select_slider("选择年级", options=["一/二年级", "三/四年级", "五/六年级"], value="三/四年级")
    voice_choice = st.selectbox("🔊 朗读声音", ["👩‍🏫 温柔女老师 (知厨)", "👨‍🏫 阳光男老师 (知达)"])
    st.markdown("---")
    app_url = "https://share.streamlit.io"
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(app_url)
    qr.make(fit=True)
    st.image(qr.make_image(fill='black', back_color='white').get_image(), caption="手机扫码使用")

# --- 4. 主界面布局 (UI重构) ---

# 标题区
st.markdown("<h1>🎓 小学语文作文批改宝</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888; font-size: 14px;'>📸 拍照即改 | 📝 深度点评 | 🎙️ 语音朗读</p>", unsafe_allow_html=True)

# 🌟 核心改动：使用 Tabs 选项

import streamlit as st
from dashscope import MultiModalConversation, Generation
from dashscope.audio.tts import SpeechSynthesizer
import dashscope
from PIL import Image, ImageDraw, ImageFont
import tempfile
import os
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
    initial_sidebar_state="collapsed"
)

# --- 🎨 样式优化 ---
st.markdown("""
    <style>
    /* 全局背景：柔和米色 */
    .stApp { background-color: #FFFBF0; }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 🌟 品牌横幅 (Brand Banner) */
    .brand-banner {
        background: linear-gradient(135deg, #FF9F43 0%, #FF6B6B 100%);
        padding: 30px 20px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 10px 20px rgba(255, 107, 107, 0.2);
        margin-bottom: 30px;
        color: white;
    }
    
    /* 标题样式：支持换行优化 */
    .brand-title {
        font-family: "Microsoft YaHei", sans-serif;
        font-weight: 800;
        font-size: 2.4rem; /* 稍微加大 */
        margin: 0;
        line-height: 1.3; /* 行间距 */
        letter-spacing: 2px;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .brand-slogan {
        font-size: 1rem;
        opacity: 0.95;
        margin-top: 15px;
        font-weight: 500;
        letter-spacing: 1px;
    }
    
    /* 选项卡样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #fff;
        border-radius: 12px;
        color: #666;
        font-weight: bold;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        border: 1px solid #f0f0f0;
        flex: 1;
        padding: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FF9F43 !important;
        color: white !important;
        border: none;
        box-shadow: 0 4px 10px rgba(255, 159, 67, 0.3);
    }
    
    /* 按钮样式 */
    .stButton>button {
        width: 100%;
        border-radius: 30px;
        height: 55px;
        font-size: 18px !important;
        font-weight: bold;
        border: none;
        background: linear-gradient(135deg, #FFB74D 0%, #FF9800 100%);
        color: white;
        box-shadow: 0 6px 15px rgba(255, 152, 0, 0.25);
    }
    .stButton>button:hover {
        color: white !important;
        transform: scale(1.02);
    }

    /* 结果卡片 */
    div.css-card {
        background-color: white;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        border-top: 5px solid #FF9F43;
        margin-top: 20px;
    }
    
    /* 上传框样式 */
    div[data-testid="stFileUploader"] {
        padding: 15px;
        border: 2px dashed #FFCC80;
        border-radius: 15px;
        background-color: #fff;
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

# --- 🛠️ 工具函数 ---
def compress_image(image, max_width=1024):
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    return image

def generate_audio_dashscope(text, voice_name):
    voice_map = {
        "👩‍🏫 温柔女老师": "sambert-zhichu-v1",
        "👨‍🏫 阳光男老师": "sambert-zhida-v1"
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

# --- 3. 核心界面布局 ---

# 🌟 优化后的品牌横幅：标题分为两行，更加大气
st.markdown("""
<div class="brand-banner">
    <h1 class="brand-title">小学语文作文<br>批改宝</h1>
    <p class="brand-slogan">📸 拍照即改 | 📝 深度点评 | 🎙️ 语音朗读</p>
</div>
""", unsafe_allow_html=True)

# 🌟 设置区域 (移除了外层的 div 卡片，彻底解决了“白条”问题)
st.markdown('<p style="color: #E67E22; font-weight: bold; margin-bottom: 5px; font-size: 1.1rem; text-align: left;">🛠️ 批改偏好设置</p>', unsafe_allow_html=True)

# 直接使用 Streamlit 列布局，不加 HTML wrapper
c_set1, c_set2 = st.columns(2)
with c_set1:
    grade = st.select_slider("🎓 选择年级", options=["一/二年级", "三/四年级", "五/六年级"], value="三/四年级")
with c_set2:
    voice_choice = st.selectbox("🔊 朗读声音", ["👩‍🏫 温柔女老师", "👨‍🏫 阳光男老师"])

# 增加一点间距
st.markdown("---")

# 上传区域
tab_cam, tab_doc = st.tabs(["📸 拍照片 (推荐)", "📄 传文档"])

uploaded_imgs = None
uploaded_docs = None

with tab_cam:
    st.info("👇 适合手写作文，点击下方按钮拍照：")
    uploaded_imgs = st.file_uploader(
        "点击这里上传图片 (支持多选)", 
        type=['png', 'jpg', 'jpeg'], 
        accept_multiple_files=True,
        key="img_uploader"
    )

with tab_doc:
    st.info("👇 适合电子版，点击下方按钮选择文件：")
    uploaded_docs = st.file_uploader(
        "点击这里上传Word或PDF", 
        type=['docx', 'pdf'], 
        accept_multiple_files=True,
        key="doc_uploader"
    )

# --- 4. 逻辑处理 ---
final_file = None
file_type = ""
is_multiple_imgs = False
img_list_to_stitch = []

if uploaded_docs:
    final_file = uploaded_docs[0]
    file_type = final_file.name.split('.')[-1].lower()
elif uploaded_imgs:
    if len(uploaded_imgs) > 1:
        is_multiple_imgs = True
        img_list_to_stitch = uploaded_imgs
        file_type = "jpg"
    else:
        final_file = uploaded_imgs[0]
        file_type = final_file.name.split('.')[-1].lower()

if final_file or is_multiple_imgs:
    # 预览区
    with st.container():
        if is_multiple_imgs or file_type in ['png', 'jpg', 'jpeg']:
            if is_multiple_imgs:
                st.success(f"🧩 已拼接 {len(uploaded_imgs)} 张图片")
                image = stitch_images(img_list_to_stitch) 
                file_name_for_tmp = "stitched.jpg"
            else:
                image = Image.open(final_file)
                image = compress_image(image)
                file_name_for_tmp = final_file.name
                
            st.image(image, caption='预览', use_container_width=True)
            
            file_suffix = os.path.splitext(file_name_for_tmp)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
                image.save(tmp_file)
                tmp_file_path = tmp_file.name

            if st.button("🔍 开始识别文字"):
                with st.spinner('👀 AI正在辨认字迹...'):
                    try:
                        msg = [{'role': 'user', 'content': [{'image': f"file://{tmp_file_path}"}, {'text': 'OCR识别，仅输出作文正文。'}]}]
                        resp = MultiModalConversation.call(model='qwen-vl-max', messages=msg)
                        if resp.status_code == 200:
                            st.session_state.extracted_text = resp.output.choices[0].message.content[0]['text']
                            st.rerun()
                    except Exception as e: st.error(f"错误: {e}")

        elif file_type in ['docx', 'pdf']:
            if st.button("📖 读取文档内容"):
                try:
                    if file_type == 'docx': st.session_state.extracted_text = read_docx(final_file)
                    else: st.session_state.extracted_text = read_pdf(final_file)
                    st.rerun()
                except Exception as e: st.error(f"读取失败: {e}")

    # 批改区
    if st.session_state.extracted_text:
        st.markdown("---")
        st.subheader("✍️ 确认内容")
        user_text = st.text_area("text_check", value=st.session_state.extracted_text, height=150, label_visibility="collapsed")
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✨ 智能批改 (Turbo加速版)"):
            with st.spinner('⚡ 老师正在批改中...'):
                grade_focus = ""
                if grade == "一/二年级": grade_focus = "侧重【敢写、能写、写完整】。鼓励为主。"
                elif grade == "三/四年级": grade_focus = "侧重【写清楚、有细节、有顺序】。"
                else: grade_focus = "侧重【有中心、有情感、有思考】。"

                prompt = f"""
                你是秉持“以评促写”理念的语文老师。批改{grade}作文。
                标准：1.基础规范(30%) 2.内容表达(30%) 3.思维情感(20%) 4.创意个性(20%)。
                侧重：{grade_focus}
                作文：{user_text}
                要求：评语温暖具体，Markdown输出：
                ### 🌟 亮点与光芒
                ### 🩺 基础诊疗室
                ### 💡 提升小锦囊
                ### 🏆 综合评价(A+/A/B及寄语)
                """
                try:
                    resp = Generation.call(model='qwen-turbo', messages=[{'role': 'user', 'content': prompt}])
                    if resp.status_code == 200:
                        st.session_state.review_result = resp.output.text
                        st.balloons()
                    else: st.error("失败")
                except Exception as e: st.error(f"错误: {e}")

        # 结果展示
        if st.session_state.review_result:
            st.markdown("<div class='css-card'>", unsafe_allow_html=True)
            st.markdown("### 📝 老师点评")
            st.markdown(st.session_state.review_result)
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔊 播放语音"):
                    with st.spinner(f"正在合成..."):
                        if generate_audio_dashscope(st.session_state.review_result, voice_choice):
                            st.audio("review.mp3")
            with c2:
                col_w, col_i = st.columns(2)
                with col_w:
                    word_file = create_word_report(st.session_state.review_result)
                    st.download_button(
                        label="📄 Word", 
                        data=word_file, 
                        file_name="report.docx", 
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                with col_i:
                    img = create_review_card(st.session_state.review_result)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    st.download_button(
                        label="🖼️ 图片", 
                        data=buf.getvalue(), 
                        file_name="card.png", 
                        mime="image/png"
                    )

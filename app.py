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
import PyPDF2
import math

# --- 1. 页面配置 ---
st.set_page_config(
    page_title="小学语文作文批改宝", # ✅ 标题已改回
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        height: 50px;
        font-weight: bold;
    }
    .stSuccess {
        background-color: #f0fdf4;
        border-radius: 10px;
    }
    .stSpinner > div {
        border-top-color: #FF4B4B !important;
    }
    /* 针对手机端上传区域的优化提示 */
    .upload-hint {
        font-size: 0.85rem;
        color: #e65100;
        background-color: #fff3e0;
        padding: 10px;
        border-radius: 8px;
        margin-top: 5px;
        border: 1px solid #ffcc80;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🎓 小学语文作文批改宝") # ✅ 标题已改回
st.caption("🚀 图片自动压缩 | 极速响应 | 智能分年级点评")

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

# --- 🛠️ 核心优化工具：图片压缩 ---
def compress_image(image, max_width=1024):
    if image.width > max_width:
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)
    return image

# --- 🛠️ 工具1：阿里语音 ---
def generate_audio_dashscope(text, voice_name):
    voice_map = {
        "👩‍🏫 温柔女老师 (知厨)": "sambert-zhichu-v1",
        "👨‍🏫 阳光男老师 (知达)": "sambert-zhida-v1",
        "👧 可爱童声 (知甜)": "sambert-zhitian-v1",
        "🎙️ 新闻播报 (知妙)": "sambert-zhimiao-v1"
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

# --- 🛠️ 工具2：下载字体 ---
@st.cache_resource
def get_font():
    font_path = "SimHei.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
        try:
            with st.spinner("首次运行，正在加载资源..."):
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    with open(font_path, "wb") as f:
                        f.write(r.content)
        except: return None 
    return font_path

# --- 🛠️ 工具3：生成长图卡片 ---
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
        
    # ✅ 底部水印改回原名
    draw.text((margin, img_height - 50), "🤖 小学语文作文批改宝", fill=(150, 150, 150), font=content_font)
    
    return img

# --- 🛠️ 工具4：文件处理 ---
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

# --- 3. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 设置")
    grade = st.select_slider("选择年级", options=["一/二年级", "三/四年级", "五/六年级"], value="三/四年级")
    voice_choice = st.selectbox(
        "🔊 选择朗读声音",
        ["👩‍🏫 温柔女老师 (知厨)", "👨‍🏫 阳光男老师 (知达)", "👧 可爱童声 (知甜)", "🎙️ 新闻播报 (知妙)"]
    )
    st.markdown("---")
    st.header("📤 上传")
    
    # ✅ 重点修复：上传区域增加文字说明
    uploaded_files = st.file_uploader(
        "支持 图片 / Word / PDF", 
        type=['png', 'jpg', 'jpeg', 'docx', 'pdf'], 
        accept_multiple_files=True
    )
    # 🌟 专门为手机用户增加的提示
    st.markdown("""
    <div class="upload-hint">
        📱 <b>手机端提示：</b><br>
        如果要上传 <b>Word</b> 或 <b>PDF</b>，点击上传后请选择 <b>“浏览”</b> 或 <b>“文件”</b> (Files)，不要只点击“照片图库”。
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    app_url = "https://share.streamlit.io"
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(app_url)
    qr.make(fit=True)
    st.image(qr.make_image(fill='black', back_color='white').get_image(), caption="手机扫码使用")

# --- 4. 主逻辑 ---
if uploaded_files:
    file_type = uploaded_files[0].name.split('.')[-1].lower()
    
    if file_type in ['png', 'jpg', 'jpeg']:
        if len(uploaded_files) > 1:
            st.info(f"📸 拼接 {len(uploaded_files)} 张图片...")
            image = stitch_images(uploaded_files) 
        else:
            image = Image.open(uploaded_files[0])
            image = compress_image(image)
            
        st.image(image, caption='预览(已自动压缩)', use_container_width=True)
        
        file_suffix = os.path.splitext(uploaded_files[0].name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
            image.save(tmp_file)
            tmp_file_path = tmp_file.name

        if st.button("🔍 识别文字", type="primary"):
            with st.spinner('👀 识别中...'):
                try:
                    msg = [{'role': 'user', 'content': [{'image': f"file://{tmp_file_path}"}, {'text': 'OCR识别。'}]}]
                    resp = MultiModalConversation.call(model='qwen-vl-max', messages=msg)
                    if resp.status_code == 200:
                        st.session_state.extracted_text = resp.output.choices[0].message.content[0]['text']
                        st.rerun()
                except Exception as e: st.error(f"错误: {e}")

    elif file_type in ['docx', 'pdf']:
        if st.button("📖 读取文档", type="primary"):
            try:
                if file_type == 'docx': st.session_state.extracted_text = read_docx(uploaded_files[0])
                else: st.session_state.extracted_text = read_pdf(uploaded_files[0])
                st.rerun()
            except Exception as e: st.error(f"读取失败: {e}")

    if st.session_state.extracted_text:
        st.markdown("### 📝 确认内容")
        user_text = st.text_area("内容", value=st.session_state.extracted_text, height=150)
        
        if st.button("✨ 智能批改", type="primary"):
            with st.spinner('⚡ 老师正在批改...'):
                s_prompt = "亲切鼓励" if grade == "一/二年级" else "客观专业"
                prompt = f"你是语文老师。批改{grade}作文。语气：{s_prompt}。作文：{user_text}。按Markdown输出：亮点、诊断、建议、评级。"
                try:
                    # ✅ 保持使用 Turbo 模型以确保速度
                    resp = Generation.call(model='qwen-turbo', messages=[{'role': 'user', 'content': prompt}])
                    if resp.status_code == 200:
                        st.session_state.review_result = resp.output.text
                        st.success("完成！")
                    else: st.error("失败")
                except Exception as e: st.error(f"错误: {e}")

        if st.session_state.review_result:
            st.markdown("---")
            st.markdown(st.session_state.review_result)
            
            st.markdown("### 🎁 功能区")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔊 播放语音点评"):
                    with st.spinner(f"正在生成语音..."):
                        if generate_audio_dashscope(st.session_state.review_result, voice_choice):
                            st.audio("review.mp3")
            with c2:
                img = create_review_card(st.session_state.review_result)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                st.download_button("🖼️ 下载评语卡片", data=buf.getvalue(), file_name="评语.png", mime="image/png")

else:
    st.info("👈 请上传文件")

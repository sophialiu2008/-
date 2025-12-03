import streamlit as st
from dashscope import MultiModalConversation, Generation
import dashscope
from PIL import Image, ImageDraw, ImageFont
import tempfile
import os
import qrcode
import io
import requests
from gtts import gTTS
import docx
import PyPDF2

# --- 1. 页面配置与美化 (UI升级) ---
st.set_page_config(
    page_title="小学作文批改精灵", 
    page_icon="🎓",
    layout="mobile", # 布局优化
    initial_sidebar_state="expanded"
)

# 自定义 CSS：隐藏菜单，美化按钮，适配手机
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
    h1 {
        color: #FF4B4B;
        font-size: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🎓 小学作文批改精灵")
st.caption("🚀 支持 图片 / Word / PDF | 智能分年级点评 | 生成评语卡片")

# --- 2. 基础配置与工具函数 ---
api_key = st.secrets.get("DASHSCOPE_API_KEY")
if not api_key:
    st.error("⚠️ 请配置 API Key")
    st.stop()
dashscope.api_key = api_key

# 初始化状态
if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = ""
if 'review_result' not in st.session_state:
    st.session_state.review_result = ""

# --- 🛠️ 工具1：下载中文字体 (用于生成图片) ---
@st.cache_resource
def get_font():
    font_path = "SimHei.ttf"
    if not os.path.exists(font_path):
        # 从 GitHub 镜像下载一个免费商用字体 (文泉驿微米黑)
        url = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
        try:
            with st.spinner("首次运行，正在下载字体文件..."):
                r = requests.get(url)
                with open(font_path, "wb") as f:
                    f.write(r.content)
        except:
            return None # 下载失败则使用默认
    return font_path

# --- 🛠️ 工具2：生成评语图片 ---
def create_review_card(text, student_name="同学"):
    font_path = get_font()
    # 创建白色背景图
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), color=(255, 255, 245))
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
        content_font = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        content_font = ImageFont.load_default()

    # 绘制标题
    draw.text((40, 40), "🏆 作文批改报告", fill=(255, 75, 75), font=title_font)
    draw.line((40, 100, 760, 100), fill=(200, 200, 200), width=2)
    
    # 简单的文字换行处理
    margin = 40
    y_text = 120
    lines = text.split('\n')
    
    for line in lines:
        # 简单处理：如果行太长就切断（更完美的换行需要复杂计算，这里简化处理）
        if len(line) > 35: 
            line = line[:35] + "..." 
        draw.text((margin, y_text), line, fill=(50, 50, 50), font=content_font)
        y_text += 35
        if y_text > height - 100: break # 防止超出图片
        
    draw.text((margin, height-60), "🤖 AI 批改助手生成", fill=(150, 150, 150), font=content_font)
    return img

# --- 🛠️ 工具3：文件解析 (Word/PDF) ---
def read_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

def read_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# --- 🛠️ 工具4：图片拼接 ---
def stitch_images(image_list):
    if not image_list: return None
    images = [Image.open(x) for x in image_list]
    widths, heights = zip(*(i.size for i in images))
    new_im = Image.new('RGB', (max(widths), sum(heights)), (255, 255, 255))
    y_offset = 0
    for im in images:
        new_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    return new_im

# --- 3. 侧边栏设置 ---
with st.sidebar:
    st.header("⚙️ 批改设置")
    
    # 🌟 功能：年级选择
    grade = st.select_slider(
        "选择学生年级", 
        options=["一/二年级", "三/四年级", "五/六年级"],
        value="三/四年级"
    )
    
    st.markdown("---")
    st.header("📤 上传文件")
    # 🌟 功能：多格式支持
    uploaded_files = st.file_uploader(
        "支持 图片 / Word / PDF", 
        type=['png', 'jpg', 'jpeg', 'docx', 'pdf'], 
        accept_multiple_files=True
    )
    
    st.markdown("---")
    # 二维码展示
    app_url = "https://share.streamlit.io" # 请替换为你的真实网址
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(app_url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill='black', back_color='white')
    st.image(img_qr.get_image(), caption="手机扫码使用")

# --- 4. 主逻辑处理 ---
if uploaded_files:
    file_type = uploaded_files[0].name.split('.')[-1].lower()
    
    # === 情况A: 处理图片 (OCR) ===
    if file_type in ['png', 'jpg', 'jpeg']:
        if len(uploaded_files) > 1:
            st.info(f"📸 检测到 {len(uploaded_files)} 张图片，正在拼接...")
            image = stitch_images(uploaded_files)
        else:
            image = Image.open(uploaded_files[0])
            
        st.image(image, caption='预览图', use_container_width=True)
        
        # 存临时文件供 API 使用
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
            image.save(tmp_file, format='JPEG')
            tmp_file_path = tmp_file.name

        if st.button("🔍 开始识别文字", type="primary"):
            with st.spinner('👀 AI正在努力辨认字迹...'):
                try:
                    ocr_msg = [
                        {'role': 'system', 'content': [{'text': '你是一个OCR助手。请将图片中的手写作文完整转录为文字。不要进行修改。'}]},
                        {'role': 'user', 'content': [{'image': f"file://{tmp_file_path}"}, {'text': '请识别图中的文字。'}]}
                    ]
                    resp = MultiModalConversation.call(model='qwen-vl-max', messages=ocr_msg)
                    if resp.status_code == 200:
                        st.session_state.extracted_text = resp.output.choices[0].message.content[0]['text']
                        st.rerun()
                    else:
                        st.error(f"识别失败: {resp.message}")
                except Exception as e:
                    st.error(f"错误: {e}")

    # === 情况B: 处理文档 (Word/PDF) ===
    elif file_type in ['docx', 'pdf']:
        st.info(f"📄 检测到文档: {uploaded_files[0].name}")
        if st.button("📖 读取文档内容", type="primary"):
            try:
                if file_type == 'docx':
                    st.session_state.extracted_text = read_docx(uploaded_files[0])
                else:
                    st.session_state.extracted_text = read_pdf(uploaded_files[0])
                st.rerun()
            except Exception as e:
                st.error(f"读取失败: {e} (请确保PDF是文字版而非扫描版)")

    # === 阶段二：显示文字与批改 ===
    if st.session_state.extracted_text:
        st.markdown("### 📝 作文内容确认")
        user_text = st.text_area("请核对文字（可修改）", value=st.session_state.extracted_text, height=200)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("✨ 智能批改", type="primary"):
                with st.spinner('🤖 老师正在思考...'):
                    # 🌟 动态 Prompt：根据年级调整语气
                    style_prompt = ""
                    if grade == "一/二年级":
                        style_prompt = "语气要像幼儿园老师一样亲切，多用‘真棒’、‘加油’，重点关注错别字和标点，不要讲太深的道理。"
                    elif grade == "三/四年级":
                        style_prompt = "语气要鼓励为主，重点关注句子是否通顺，描写是否生动，给出具体的修改建议。"
                    else:
                        style_prompt = "语气要专业客观，重点关注文章结构、逻辑表达和修辞手法，像对待小作家一样点评。"

                    prompt = f"""
                    你是一位小学语文老师。请批改以下{grade}学生的作文。
                    **要求**：{style_prompt}
                    
                    **作文**：{user_text}
                    
                    **请按以下Markdown格式输出**：
                    ### 🌟 亮点
                    ### 🩺 诊断
                    ### 💡 建议
                    ### 🏆 评级 (A/B/C)
                    """
                    try:
                        resp = Generation.call(model='qwen-plus', messages=[{'role': 'user', 'content': prompt}])
                        if resp.status_code == 200:
                            st.session_state.review_result = resp.output.text
                            st.success("批改完成！")
                        else:
                            st.error("批改失败")
                    except Exception as e:
                        st.error(f"错误: {e}")

        # === 阶段三：结果展示与功能 ===
        if st.session_state.review_result:
            st.markdown("---")
            st.markdown(st.session_state.review_result)
            
            # 🌟 功能：生成图片 & 语音
            st.markdown("### 🎁 更多功能")
            c1, c2 = st.columns(2)
            
            with c1:
                # 语音朗读
                if st.button("🔊 播放语音"):
                    text_clean = st.session_state.review_result.replace("*", "").replace("#", "")
                    try:
                        tts = gTTS(text=text_clean[:500], lang='zh-cn') # 限制长度防止超时
                        tts.save("review.mp3")
                        st.audio("review.mp3")
                    except Exception as e:
                        st.warning("语音服务繁忙，请稍后再试。")

            with c2:
                # 生成图片卡片
                img = create_review_card(st.session_state.review_result)
                # 转换为字节流供下载
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                byte_im = buf.getvalue()
                
                st.download_button(
                    label="🖼️ 下载评语图片",
                    data=byte_im,
                    file_name="作文批改报告.png",
                    mime="image/png"
                )

else:
    st.info("👈 请点击左上角箭头，上传文件开始批改")

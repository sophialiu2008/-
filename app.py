import streamlit as st
from dashscope import MultiModalConversation, Generation
import dashscope
from PIL import Image
import tempfile
import os
import qrcode
import io

# --- 1. 页面基础配置 ---
st.set_page_config(
    page_title="小学作文批改助手", 
    page_icon="📝",
    layout="centered"
)

# 隐藏不需要的菜单
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

st.title("📝 小学作文批改助手")
st.markdown("##### 👩‍🏫 专为教师设计：多页拍照 -> 自动拼接 -> 智能批改")

# --- 2. 安全检查 ---
api_key = st.secrets.get("DASHSCOPE_API_KEY")
if not api_key:
    st.error("⚠️ 系统未配置 API Key，请联系管理员。")
    st.stop()
dashscope.api_key = api_key

# --- 3. 状态管理 ---
if 'ocr_result' not in st.session_state:
    st.session_state.ocr_result = ""
if 'review_result' not in st.session_state:
    st.session_state.review_result = ""

# --- 4. 侧边栏：上传区 + 二维码 ---
with st.sidebar:
    st.header("📤 上传作文")
    # 🌟 修改点：accept_multiple_files=True 允许上传多张
    uploaded_files = st.file_uploader("点击拍照或上传图片 (支持多页)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    st.caption("💡 提示：如果是多页作文，请按顺序选择或拍摄。")
    
    st.markdown("---")
    st.markdown("### 📱 手机扫码使用")
    app_url = "https://zcrrkfc8pqdshl4j64ijb4.streamlit.app/" # 建议替换为你部署后的真实网址
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(app_url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill='black', back_color='white')
    img_byte_arr = io.BytesIO()
    img_qr.save(img_byte_arr, format='PNG')
    st.image(img_byte_arr.getvalue(), caption="老师可以用微信扫一扫", use_container_width=True)

# --- 🌟 辅助函数：图片拼接 ---
def stitch_images(image_list):
    if not image_list:
        return None
    images = [Image.open(x) for x in image_list]
    # 计算总宽度和总高度
    widths, heights = zip(*(i.size for i in images))
    total_width = max(widths)
    total_height = sum(heights)
    
    # 创建空白长图
    new_im = Image.new('RGB', (total_width, total_height), (255, 255, 255))
    
    # 竖向拼接
    y_offset = 0
    for im in images:
        # 如果图片宽度不一致，居中放置（可选，这里简单起见直接左对齐）
        new_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    
    return new_im

# --- 5. 主功能区 ---
if uploaded_files:
    # 🌟 修改点：处理多张图片
    if len(uploaded_files) > 1:
        st.info(f"检测到 {len(uploaded_files)} 页作文，正在自动拼接...")
        # 调用拼接函数
        image = stitch_images(uploaded_files)
        st.image(image, caption='已拼接的作文长图', use_container_width=True)
    else:
        # 只有一张图的情况
        image = Image.open(uploaded_files[0])
        st.image(image, caption='学生作文原图', use_container_width=True)
    
    # 保存图片到临时文件 (无论是单张还是拼接后的长图，都存为一个文件)
    # 使用 .jpg 后缀
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
        image.save(tmp_file, format='JPEG') # 统一转存为 JPEG
        tmp_file_path = tmp_file.name

    # === 阶段一：智能识别 ===
    if st.button("🔍 第一步：识别文字", type="primary"):
        with st.spinner('👀 正在努力辨认字迹...'):
            try:
                ocr_messages = [
                    {'role': 'system', 'content': [{'text': '你是一个OCR助手。请将图片中的手写作文完整转录为文字。不要进行修改，只输出正文。'}]},
                    {'role': 'user', 'content': [{'image': f"file://{tmp_file_path}"}, {'text': '请识别图中的文字。'}]}
                ]
                resp = MultiModalConversation.call(model='qwen-vl-max', messages=ocr_messages)
                
                if resp.status_code == 200:
                    st.session_state.ocr_result = resp.output.choices[0].message.content[0]['text']
                    st.rerun()
                else:
                    st.error(f"识别失败: {resp.message}")
            except Exception as e:
                st.error(f"系统错误: {e}")

    # === 阶段二：人工确认 ===
    if st.session_state.ocr_result:
        st.markdown("---")
        st.subheader("✍️ 确认文字内容")
        user_text = st.text_area("识别结果", value=st.session_state.ocr_result, height=200)

        # === 阶段三：AI 批改 ===
        if st.button("✨ 确认无误，生成评语", type="primary"):
            with st.spinner('🤖 正在分析作文逻辑与文采...'):
                prompt = f"""
                你是一位拥有20年经验的小学语文特级教师。请批改以下作文。
                **学生作文**：{user_text}
                **请按以下 Markdown 格式输出评语**：
                ### 🌟 亮点与鼓励
                ### 🩺 字词小诊所
                ### 💡 提升建议
                ### 🏆 综合评分
                """
                try:
                    resp = Generation.call(model='qwen-plus', messages=[{'role': 'user', 'content': prompt}])
                    if resp.status_code == 200:
                        st.session_state.review_result = resp.output.text
                        st.success("批改完成！")
                    else:
                        st.error("生成评语失败")
                except Exception as e:
                    st.error(f"错误: {e}")

    # === 阶段四：展示结果 ===
    if st.session_state.review_result:
        st.markdown("---")
        st.subheader("📝 批改报告")
        st.markdown(st.session_state.review_result)
        st.balloons()

else:
    st.info("👈 请点击左上角箭头打开菜单，上传作文照片（支持多选）。")

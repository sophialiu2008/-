import streamlit as st
from dashscope import MultiModalConversation, Generation
import dashscope
from PIL import Image
import io
import asyncio
import edge_tts
import nest_asyncio
import tempfile
import os
import re  # 👈 新增：用来清洗文字中的符号

# 解决 Streamlit 中的异步循环问题
nest_asyncio.apply()

# --- 页面配置 ---
st.set_page_config(page_title="小学作文智能批改 Pro", page_icon="📝")
st.title("📝 小学作文智能批改 Pro")
st.markdown("### 📸 流程：拍照 -> 确认文字 -> 智能批改 + 语音朗读")

# --- 获取 API Key ---
api_key = st.secrets.get("DASHSCOPE_API_KEY")
if not api_key:
    st.error("请先在 Streamlit Secrets 中配置 DASHSCOPE_API_KEY")
    st.stop()
dashscope.api_key = api_key

# --- 初始化 Session State ---
if 'ocr_result' not in st.session_state:
    st.session_state.ocr_result = ""
if 'review_result' not in st.session_state:
    st.session_state.review_result = ""

# --- 🌟 新增辅助函数：清洗 Markdown 符号 ---
def clean_markdown(text):
    # 去除 **加粗**
    text = text.replace("**", "")
    text = text.replace("__", "")
    # 去除 ### 标题
    text = text.replace("### ", " ").replace("## ", " ").replace("# ", " ")
    # 去除列表符号 - 
    text = text.replace("- ", " ")
    return text

# --- 辅助函数：生成语音 ---
async def text_to_speech(text, output_file="review.mp3"):
    # 先清洗文字，防止特殊符号导致语音引擎报错
    clean_text = clean_markdown(text)
    
    # 限制长度，防止文本太长导致超时（截取前500字，通常够读点评了）
    if len(clean_text) > 800:
        clean_text = clean_text[:800] + "..."
        
    communicate = edge_tts.Communicate(clean_text, "zh-CN-XiaoxiaoNeural")
    await communicate.save(output_file)

# --- 侧边栏：上传图片 ---
with st.sidebar:
    st.header("1. 上传作文")
    uploaded_file = st.file_uploader("请上传作文图片", type=['png', 'jpg', 'jpeg'])

# --- 主界面逻辑 ---
if uploaded_file is not None:
    # 1. 展示图片
    image = Image.open(uploaded_file)
    st.image(image, caption='已上传的作文', use_container_width=True)
    
    file_suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name

    # 2. 第一步：识别文字
    if st.button("🔍 第一步：识别文字"):
        with st.spinner('正在努力辨认字迹...'):
            try:
                ocr_messages = [
                    {
                        "role": "system",
                        "content": [{"text": "你是一个OCR助手。请将图片中的手写作文完整转录为文字。不要进行修改，不要添加任何评论，只输出识别到的正文内容。"}]
                    },
                    {
                        "role": "user",
                        "content": [
                            {"image": f"file://{tmp_file_path}"},
                            {"text": "请识别图中的文字。"}
                        ]
                    }
                ]
                
                response = MultiModalConversation.call(model='qwen-vl-max', messages=ocr_messages)
                
                if response.status_code == 200:
                    raw_text = response.output.choices[0].message.content[0]['text']
                    st.session_state.ocr_result = raw_text 
                    st.success("识别成功！请在下方核对。")
                else:
                    st.error(f"识别失败: {response.message}")
            except Exception as e:
                st.error(f"发生错误: {str(e)}")

    # 3. 第二步：人工校对
    if st.session_state.ocr_result:
        st.markdown("---")
        st.header("2. 确认文字内容")
        user_edited_text = st.text_area("作文内容", value=st.session_state.ocr_result, height=200)

        # 4. 第三步：生成点评
        if st.button("✨ 确认无误，开始批改"):
            with st.spinner('老师正在批改中...'):
                grade_prompt = f"""
                你是一位亲切的小学语文老师。请根据学生作文内容进行批改。
                **作文内容**：{user_edited_text}
                **批改要求**（Markdown格式）：
                1. **【暖心点评】**：先肯定优点。
                2. **【字词诊所】**：指出具体的错别字、病句。
                3. **【佳句摘抄】**：找出文中写得好的句子。
                4. **【提升建议】**：给出一个具体的改进方向。
                语气要温柔、鼓励为主，适合小学生阅读。
                """
                try:
                    response = Generation.call(model='qwen-plus', messages=[{'role': 'user', 'content': grade_prompt}])
                    if response.status_code == 200:
                        st.session_state.review_result = response.output.text
                        st.success("批改完成！")
                    else:
                        st.error("批改失败，请重试。")
                except Exception as e:
                    st.error(f"发生错误: {str(e)}")

    # 5. 第四步：展示结果与语音
    if st.session_state.review_result:
        st.markdown("---")
        st.header("3. 老师点评")
        st.markdown(st.session_state.review_result)
        
        st.markdown("---")
        st.header("🔊 听老师说")
        
        # 🌟 修复：增加了错误处理 (try-except)，防止语音失败导致报错
        if st.button("播放语音点评"):
            with st.spinner("正在合成语音（请耐心等待）..."):
                try:
                    # 删除旧文件防止缓存干扰
                    if os.path.exists("review.mp3"):
                        os.remove("review.mp3")
                        
                    asyncio.run(text_to_speech(st.session_state.review_result))
                    st.audio("review.mp3", format="audio/mp3")
                except Exception as e:
                    # 就算语音失败了，也不要红屏报错，而是温柔提示
                    st.warning(f"语音合成暂时不可用 (网络原因或文字符号问题)，请直接阅读文字点评。\n技术详情: {e}")

else:
    st.info("👈 请先在左侧上传一张作文照片")

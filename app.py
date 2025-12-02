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

# --- 初始化 Session State (用来“记住”变量) ---
if 'ocr_result' not in st.session_state:
    st.session_state.ocr_result = ""
if 'review_result' not in st.session_state:
    st.session_state.review_result = ""

# --- 辅助函数：生成语音 ---
async def text_to_speech(text, output_file="review.mp3"):
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
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
    
    # 🌟 核心修复：将上传的文件保存为本地临时文件，获取路径
    # 因为 dashscope API 需要读取本地路径，不能直接读 streamlit 的对象
    file_suffix = os.path.splitext(uploaded_file.name)[1] # 获取文件后缀 (.jpg 等)
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_file_path = tmp_file.name # 拿到这个临时文件的绝对路径

    # 2. 第一步：识别文字 (OCR)
    if st.button("🔍 第一步：识别文字"):
        with st.spinner('正在努力辨认字迹...'):
            try:
                # 专门的 Prompt 让模型只做识别
                ocr_messages = [
                    {
                        "role": "system",
                        "content": [{"text": "你是一个OCR助手。请将图片中的手写作文完整转录为文字。不要进行修改，不要添加任何评论，只输出识别到的正文内容。"}]
                    },
                    {
                        "role": "user",
                        "content": [
                            # 🌟 这里改成了 file:// 加上本地路径
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
        st.info("如果AI看错了，请在下方直接修改，然后点击批改。")
        
        user_edited_text = st.text_area("作文内容", value=st.session_state.ocr_result, height=200)

        # 4. 第三步：生成点评
        if st.button("✨ 确认无误，开始批改"):
            with st.spinner('老师正在批改中...'):
                grade_prompt = f"""
                你是一位亲切的小学语文老师。请根据学生作文内容进行批改。
                
                **作文内容**：
                {user_edited_text}

                **批改要求**（Markdown格式）：
                1. **【暖心点评】**：先肯定优点（如“字迹工整”、“想象力丰富”）。
                2. **【字词诊所】**：指出具体的错别字、病句，并给出修改意见。
                3. **【佳句摘抄】**：找出文中写得好的句子。
                4. **【提升建议】**：给出一个具体的改进方向（如“多用一些形容词”）。
                
                语气要温柔、鼓励为主，适合小学生阅读。
                """
                
                try:
                    # 使用 qwen-plus 进行纯文本批改
                    response = Generation.call(model='qwen-plus', messages=[{'role': 'user', 'content': grade_prompt}])
                    
                    if response.status_code == 200:
                        review_content = response.output.text
                        st.session_state.review_result = review_content
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
        if st.button("播放语音点评"):
            with st.spinner("正在合成语音..."):
                asyncio.run(text_to_speech(st.session_state.review_result))
                st.audio("review.mp3")

else:
    st.info("👈 请先在左侧上传一张作文照片")

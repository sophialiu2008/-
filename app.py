import streamlit as st
from dashscope import MultiModalConversation
import dashscope
from PIL import Image
import io

# 页面配置
st.set_page_config(page_title="小学作文智能批改", page_icon="📝")

st.title("📝 小学作文智能批改助手")
st.markdown("### 📸 拍照上传，老师帮你改作文！")

# 获取 API Key (稍后在 Streamlit 后台配置)
api_key = st.secrets.get("DASHSCOPE_API_KEY")

if not api_key:
    st.error("请先在 Streamlit Secrets 中配置 DASHSCOPE_API_KEY")
    st.stop()

dashscope.api_key = api_key

# 上传图片组件
uploaded_file = st.file_uploader("请上传作文图片 (支持手机拍照)", type=['png', 'jpg', 'jpeg'])

# 定义提示词 (Prompt) - 这是核心灵魂
system_prompt = """
你是一位拥有20年教龄的小学语文老师，亲切、耐心、循循善诱。
你的任务是根据学生上传的作文图片进行批改。

请按以下步骤输出（使用Markdown格式）：
1. **【原文识别】**：尽力准确识别图片中的手写文字，并展示出来。如果有个别字看不清，结合上下文推断。
2. **【总体点评】**：用鼓励性的语言（如“真棒”、“进步很大”）开头，简要评价作文的立意和完整度。
3. **【字词纠错】**：指出具体的错别字或标点错误，格式为：“错误处 -> 正确写法”。
4. **【佳句赏析】**：找出文中写得好的句子，给予表扬。
5. **【改进建议】**：针对句子不通顺或逻辑不清的地方，给出具体的修改建议（适合小学生理解的建议）。
"""

if uploaded_file is not None:
    # 展示图片
    image = Image.open(uploaded_file)
    st.image(image, caption='已上传的作文', use_container_width=True)
    
    # 转换图片格式以供 API 使用
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format=image.format)
    img_byte_arr = img_byte_arr.getvalue()

    if st.button("开始批改 ✨"):
        with st.spinner('老师正在认真看你的作文，请稍等...'):
            try:
                # 调用 Qwen-VL-Max 模型
                messages = [
                    {
                        "role": "system",
                        "content": [{"text": system_prompt}]
                    },
                    {
                        "role": "user",
                        "content": [
                            {"image": uploaded_file}, # Streamlit 上传对象直接传入
                            {"text": "请帮我批改这篇作文。"}
                        ]
                    }
                ]
                
                # 注意：这里使用 dashscope 的多模态调用方式
                response = MultiModalConversation.call(
                    model='qwen-vl-max', # 使用通义千问视觉大模型
                    messages=messages
                )

                if response.status_code == 200:
                    result_text = response.output.choices[0].message.content[0]['text']
                    st.success("批改完成！")
                    st.markdown("---")
                    st.markdown(result_text)
                else:
                    st.error(f"调用失败: {response.code} - {response.message}")

            except Exception as e:
                # 简单的错误处理，防止直接报错
                # 有时候是图片格式问题，有时候是网络问题
                st.error(f"发生错误: {str(e)}")
                st.info("建议：请确保图片清晰，方向正确。")

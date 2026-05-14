import streamlit as st


st.set_page_config(page_title="Chatbot Preview", page_icon="🤖", layout="centered")

st.title("🤖 Chatbot UI Preview")
st.caption("Simple Streamlit chat layout preview")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I am your demo chatbot. Ask me anything."}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Type your message...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    reply = f"You said: {prompt}\n\n(Replace this with your real model/API response.)"
    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)

import streamlit as st
import re
from io import StringIO

st.set_page_config(page_title="SBV to SRT Converter", page_icon="🎬")

st.title("🎬 SBV to SRT Converter")
st.write("Upload your `.sbv` subtitle file and convert it into `.srt` format instantly.")

uploaded_file = st.file_uploader("Upload SBV File", type=["sbv"])

def convert_sbv_to_srt(sbv_content):
    blocks = sbv_content.strip().split("\n\n")
    srt_output = []

    for i, block in enumerate(blocks, start=1):
        lines = block.strip().split("\n")

        if len(lines) >= 2:
            time_line = lines[0]

            start_time, end_time = time_line.split(",")

            # Convert timestamps properly
            start_time = start_time.replace(".", ",")
            end_time = end_time.replace(".", ",")

            
            if len(start_time.split(":")[0]) == 1:
                start_time = "0" + start_time

            if len(end_time.split(":")[0]) == 1:
                end_time = "0" + end_time

            subtitle_text = "\n".join(lines[1:])

            srt_block = (
                f"{i}\n"
                f"{start_time} --> {end_time}\n"
                f"{subtitle_text}\n"
            )

            srt_output.append(srt_block)

    return "\n".join(srt_output)

if uploaded_file is not None:
    sbv_content = uploaded_file.read().decode("utf-8")

    srt_content = convert_sbv_to_srt(sbv_content)

    st.success("✅ Conversion Successful!")

    st.download_button(
        label="⬇ Download SRT File",
        data=srt_content,
        file_name=uploaded_file.name.replace(".sbv", ".srt"),
        mime="text/plain"
    )
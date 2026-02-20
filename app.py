import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
from xai_sdk import Client
from xai_sdk.tools import web_search

st.title("Website Text Rewriter — 5 Variants")

api_key = st.text_input("xAI API Key", type="password")
business_name = st.text_input("Business name (for address/phone lookup)")
uploaded_file = st.file_uploader("Upload website ZIP archive", type="zip")

if uploaded_file and api_key and business_name:
    if st.button("Start → Generate 5 Rewritten Versions"):
        with st.spinner("Extracting ZIP, rewriting pages via Grok... (can take time)"):
            temp_dir = tempfile.mkdtemp()
            extract_dir = os.path.join(temp_dir, "original")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            html_files = [os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.lower().endswith('.html')]

            if not html_files:
                st.error("ZIP archive has no .html files.")
                shutil.rmtree(temp_dir)
            else:
                client = Client(api_key=api_key)

                for variant in range(1, 6):
                    st.write(f"→ Processing variant {variant}/5")

                    variant_dir = os.path.join(temp_dir, f"variant_{variant}")
                    shutil.copytree(extract_dir, variant_dir, dirs_exist_ok=True)

                    for html_path in html_files:
                        with open(html_path, 'r', encoding='utf-8') as f:
                            original_html = f.read()

                        prompt = f"""
Rewrite visible text on this webpage to be unique, natural, SEO-friendly and engaging.
Keep ALL HTML structure, classes, ids, scripts, styles, links, images intact — change ONLY text content.
Search for real business contact info (address, phone) using web_search tool.
Business: '{business_name}'. Queries like: "{business_name} official address phone" or "Google Maps {business_name}".
Replace existing contacts if found; otherwise leave original or add placeholder.
Return ONLY clean HTML code — no extra text.
HTML:
{original_html}
"""

                        response = client.chat.completions.create(
                            model="grok-4",
                            messages=[
                                {"role": "system", "content": "Expert website content editor and rewriter."},
                                {"role": "user", "content": prompt}
                            ],
                            tools=[web_search()],
                            temperature=0.75 + (variant * 0.03),
                            max_tokens=16384
                        )

                        rewritten = response.choices[0].message.content.strip()

                        variant_path = html_path.replace(extract_dir, variant_dir)
                        os.makedirs(os.path.dirname(variant_path), exist_ok=True)
                        with open(variant_path, 'w', encoding='utf-8') as f:
                            f.write(rewritten)

                    # ZIP variant
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for root, _, files in os.walk(variant_dir):
                            for file in files:
                                fp = os.path.join(root, file)
                                arc = os.path.relpath(fp, variant_dir)
                                zf.write(fp, arc)

                    zip_buffer.seek(0)

                    st.download_button(
                        label=f"Download Variant {variant} (.zip)",
                        data=zip_buffer,
                        file_name=f"rewritten_variant_{variant}.zip",
                        mime="application/zip",
                        key=f"dl_{variant}"
                    )

                shutil.rmtree(temp_dir)
                st.success("Done! All 5 rewritten site variants are ready above ↓")
else:
    st.info("Fill in all fields to start.")
    if not api_key:
        st.warning("→ xAI API key required (get at https://console.x.ai)")
    if not business_name:
        st.warning("→ Business name needed for accurate contact lookup.")
    if not uploaded_file:
        st.warning("→ Upload .zip with your static website files.")

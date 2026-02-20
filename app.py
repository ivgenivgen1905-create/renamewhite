import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
from openai import OpenAI
from bs4 import BeautifulSoup  # для точного парсингу тексту
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from collections import Counter

DetectorFactory.seed = 0

st.title("Rewriter: 5 варіантів рерайту тексту сайту")

api_key = st.text_input("Введи xAI API Key", type="password")
uploaded_zip = st.file_uploader("Завантаж ZIP-архів сайту", type="zip")

if uploaded_zip and api_key:
    if st.button("Створити 5 варіантів рерайту"):
        with st.spinner("Розпаковуємо архів і рерайтимо текст..."):
            temp_dir = tempfile.mkdtemp()
            extract_dir = os.path.join(temp_dir, "orig")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(uploaded_zip, "r") as z:
                z.extractall(extract_dir)

            html_files = [os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.lower().endswith('.html')]

            if not html_files:
                st.error("У ZIP немає HTML-файлів.")
                shutil.rmtree(temp_dir)
                st.stop()

            client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=300)

            # Визначення мови
            detected_lang = "unknown"
            for html_path in html_files:
                with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                soup = BeautifulSoup(content, 'html.parser')
                text = soup.get_text().strip()
                if len(text) > 50:
                    try:
                        detected_lang = detect(text)
                        break
                    except:
                        pass
            if detected_lang == "unknown":
                detected_lang = "uk"  # дефолт українська
            lang_map = {'uk': 'Українська', 'ru': 'Російська', 'en': 'Англійська', 'fr': 'Французька', 'de': 'Німецька'}
            detected_lang_name = lang_map.get(detected_lang, "Українська")
            st.info(f"Визначено мову: {detected_lang_name}")

            # 5 варіантів
            for var_num in range(1, 6):
                st.write(f"Генеруємо варіант {var_num} з 5...")

                var_dir = os.path.join(temp_dir, f"var_{var_num}")
                shutil.copytree(extract_dir, var_dir, dirs_exist_ok=True)

                rewritten_count = 0
                for html_path in html_files:
                    var_html_path = html_path.replace(extract_dir, var_dir)
                    with open(var_html_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    soup = BeautifulSoup(content, 'html.parser')
                    # Збираємо тільки видимий текст (ігноруємо скрипти, стилі тощо)
                    for tag in soup.find_all(text=True):
                        if tag.parent.name in ['script', 'style']:
                            continue
                        if tag.strip():
                            prompt = f"""
Рефразуй тільки цей текст на мові '{detected_lang_name}': зроби унікальним, природним, привабливим.
Не додавай і не видаляй нічого — тільки рефразований текст.
Для контактів (адреса, телефон) — заміни на випадкові правдоподібні (адреса в Україні, номер +380...).
У відповіді — тільки рефразований текст, без лапок чи пояснень.
Текст:
{tag.strip()}
"""
                            try:
                                resp = client.chat.completions.create(
                                    model="grok-code-fast-1",  # швидка модель для код/тексту
                                    messages=[{"role": "user", "content": prompt}],
                                    temperature=0.7 + (var_num * 0.05),
                                    max_tokens=512
                                )
                                new_text = resp.choices[0].message.content.strip()
                                tag.replace_with(new_text)
                            except:
                                pass

                    rewritten_content = str(soup)
                    with open(var_html_path, 'w', encoding='utf-8') as f:
                        f.write(rewritten_content)
                    rewritten_count += 1

                st.info(f"Для варіанта {var_num} переписано {rewritten_count} файлів")

                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(var_dir):
                        for file in files:
                            full = os.path.join(root, file)
                            arc = os.path.relpath(full, var_dir)
                            zf.write(full, arc)

                zip_buf.seek(0)

                st.download_button(
                    label=f"Завантажити варіант {var_num}",
                    data=zip_buf,
                    file_name=f"rewritten_var_{var_num}.zip",
                    mime="application/zip"
                )

            shutil.rmtree(temp_dir)
            st.success("Всі 5 варіантів готові!")

else:
    st.warning("Введи ключ і завантаж ZIP")

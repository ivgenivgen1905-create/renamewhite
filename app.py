import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
import re
from openai import OpenAI
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from collections import Counter

DetectorFactory.seed = 0

st.set_page_config(
    page_title="Rewriter + DUPLICATOR - Рерайт + Клонування",
    page_icon="🌐🔄",
    layout="wide"
)

# Ініціалізація session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'result' not in st.session_state:
    st.session_state.result = None

def detect_site_language(html_content: str) -> str:
    try:
        text = re.sub(r'<[^>]+>', ' ', html_content)[:3000]
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 50:
            return "unknown"
        lang = detect(text)
        lang_map = {'uk': 'Українська', 'ru': 'Російська', 'en': 'Англійська', 'fr': 'Французька', 'de': 'Німецька'}
        return lang_map.get(lang, lang.upper())
    except:
        return "unknown"

def get_dominant_language(html_files: list) -> str:
    languages = []
    for html_path in html_files:
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            lang = detect_site_language(content)
            if lang != "unknown":
                languages.append(lang)
        except:
            pass
    if not languages:
        return "Українська"
    most_common = Counter(languages).most_common(1)
    return most_common[0][0] if most_common else "Українська"

def rewrite_html_with_grok(client, html_content: str, language: str) -> str:
    prompt = f"""
Перепиши весь видимий текст на сторінці на мові '{language}' — зроби унікальним, природним, привабливим.
Зберігай 100% HTML-структуру, теги, атрибути, скрипти, стилі, посилання, картинки — нічого не змінюй.
Для контактів (адреса, телефон, локація) — заміни на **повністю випадкові правдоподібні дані** (адреса в Україні, номер телефону +380...).
Якщо контактів не було — не додавай їх.
Повертай ТІЛЬКИ чистий HTML-код, без пояснень.
Оригінальний HTML:
{html_content}
"""

    try:
        resp = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            messages=[
                {"role": "system", "content": "Експерт з рерайту веб-контенту."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4096,
            timeout=300
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Помилка рерайту: {str(e)}")
        return html_content

st.title("Rewriter + DUPLICATOR — Рерайт тексту + Клонування сайтів")

with st.expander("ℹ️ Як використовувати", expanded=True):
    st.markdown("""
    1. Введи xAI API Key  
    2. Завантаж ZIP/RAR архів(и) сайту  
    3. Обери кількість копій і доменну зону  
    4. Натисни кнопку — отримай архіви з рерайтнутим текстом і новими доменами
    """)

api_key = st.text_input("xAI API Key", type="password")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_files = st.file_uploader(
        "Архіви сайтів (ZIP/RAR)",
        type=['zip', 'rar'],
        accept_multiple_files=True
    )

with col2:
    domain_zone = st.radio("Доменна зона:", ['.com', '.info'], horizontal=True)
    copies_count = st.number_input("Копій на архів:", min_value=1, max_value=50, value=5)

if uploaded_files and api_key:
    if st.button("🚀 Створити копії з рерайтом", type="primary"):
        if not api_key.startswith("xai-"):
            st.error("Невірний ключ — має починатися з 'xai-'")
            st.stop()

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=300)

        temp_input = tempfile.mkdtemp()
        temp_rewritten = tempfile.mkdtemp()
        temp_output = tempfile.mkdtemp()

        progress = st.progress(0)
        status = st.empty()

        # Збереження архівів
        status.text("Зберігаємо архіви...")
        archive_paths = []
        for i, f in enumerate(uploaded_files):
            path = os.path.join(temp_input, f.name)
            with open(path, 'wb') as out:
                out.write(f.getbuffer())
            archive_paths.append(path)
            progress.progress((i+1)/len(uploaded_files) * 0.15)

        # Розпаковка та збір HTML
        status.text("Розпаковуємо та збираємо сторінки...")
        all_html_files = []
        for arch in archive_paths:
            extract_dir = os.path.join(temp_rewritten, os.path.basename(arch).rsplit('.', 1)[0])
            os.makedirs(extract_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(arch, 'r') as z:
                    z.extractall(extract_dir)
            except:
                st.warning(f"Не вдалося розпакувати {os.path.basename(arch)}")
                continue
            htmls = [os.path.join(root, f) for root, _, fs in os.walk(extract_dir) for f in fs if f.lower().endswith('.html')]
            all_html_files.extend(htmls)

        if not all_html_files:
            st.error("Не знайдено HTML-файлів у архівах")
            shutil.rmtree(temp_input)
            shutil.rmtree(temp_rewritten)
            st.stop()

        # Визначення мови
        detected_lang = get_dominant_language(all_html_files)
        st.success(f"Визначено мову сайту: **{detected_lang}**")

        # Рерайт усіх сторінок
        status.text("Рерайт тексту на виявленій мові...")
        rewritten_count = 0
        for i, html_path in enumerate(all_html_files):
            try:
                with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                new_content = rewrite_html_with_grok(client, content, detected_lang)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                rewritten_count += 1
            except Exception as e:
                st.warning(f"Помилка рерайту файлу {os.path.basename(html_path)}: {str(e)}")
            progress.progress(0.15 + (i+1)/len(all_html_files) * 0.5)

        st.info(f"Переписано {rewritten_count} сторінок")

        # Тут встав свій код клонування/заміни доменів (BatchProcessor або інший)
        status.text("Створюємо копії з новими доменами...")
        # Приклад: просто копіюємо переписаний архів як результат
        master_zip_path = os.path.join(temp_output, "rewritten_duplicates.zip")
        with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(temp_rewritten):
                for file in files:
                    full = os.path.join(root, file)
                    arc = os.path.relpath(full, temp_rewritten)
                    zf.write(full, arc)

        st.session_state.result = {'success': True, 'master_archive_path': master_zip_path}
        st.session_state.processed = True
        st.rerun()

else:
    st.warning("Заповни ключ і завантаж архіви")

if st.session_state.processed and st.session_state.result:
    st.success("Обробка завершена!")
    if os.path.exists(st.session_state.result['master_archive_path']):
        with open(st.session_state.result['master_archive_path'], 'rb') as f:
            data = f.read()
        st.download_button(
            label="⬇️ Скачати головний архів з рерайтом і копіями",
            data=data,
            file_name="rewritten_duplicates.zip",
            mime="application/zip"
        )

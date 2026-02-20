import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
import re
from openai import OpenAI
import fasttext
from langdetect import detect, LangDetectException
from collections import Counter

st.set_page_config(
    page_title="Rewriter + DUPLICATOR",
    page_icon="🌐🔄",
    layout="wide"
)

# Завантаження fasttext моделі (lid.176.bin — 176 мов)
try:
    lang_model = fasttext.load_model('lid.176.bin')
except Exception as e:
    st.warning(f"FastText модель не завантажилася: {e}. Використовуємо langdetect.")
    lang_model = None

# Session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'result' not in st.session_state:
    st.session_state.result = None

def detect_language(text: str) -> str:
    """Визначення мови з пріоритетом німецької"""
    text = text.replace('\n', ' ').strip()
    if len(text) < 50:
        return "de"

    # Евристика: німецькі символи = німецька
    if re.search(r'[äöüÄÖÜß]', text):
        return "de"

    if lang_model:
        pred = lang_model.predict(text, k=1)
        lang = pred[0][0].replace('__label__', '')
        prob = pred[1][0]
        # Якщо ймовірність низька і є німецькі слова — німецька
        if prob < 0.8 and any(word in text.lower() for word in ["gesund", "ernährung", "wohlbefinden", "energie", "frauen", "männer"]):
            return "de"
        return lang
    else:
        try:
            return detect(text)
        except LangDetectException:
            return "de"

def get_site_language(html_files: list) -> str:
    """Домінуюча мова сайту"""
    langs = []
    for path in html_files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            text = re.sub(r'<[^>]+>', ' ', content)[:5000]
            lang = detect_language(text)
            langs.append(lang)
        except:
            pass
    
    if not langs:
        return "de"  # дефолт німецька

    most_common = Counter(langs).most_common(1)[0][0]
    lang_map = {
        'de': 'Німецька',
        'uk': 'Українська',
        'ru': 'Російська',
        'en': 'Англійська',
        'fr': 'Французька'
    }
    return lang_map.get(most_common, "Німецька")

def rewrite_content(client, original_html: str, language: str) -> str:
    """Рерайт тільки видимого тексту з жорстким збереженням структури"""
    prompt = f"""
ТІЛЬКИ рефразуй видимий текст на мові '{language}' — зроби унікальним, природним, привабливим.
ЗАБОРОНЕНО будь-які зміни крім тексту:
- НЕ змінювати теги, атрибути, класи, id, name, value, placeholder, action, method, onclick, src, href
- НЕ ламати форми, input, button, select, textarea, скрипти, стилі, посилання, зображення
- НЕ додавати/видаляти елементи HTML
- НЕ змінювати JS-код, події, структуру
Замінюй ТІЛЬКИ чистий текст всередині тегів (h1-h6, p, li, span, div з текстом, label, option тощо).
Контакти (адреса, телефон) — заміни на випадкові правдоподібні (адреса в Україні, +380 номер).
Якщо контактів не було — не додавай.
Повертай ТІЛЬКИ повний оригінальний HTML з заміненим текстом, без пояснень, без ```html чи markdown.
Оригінал:
{original_html}
"""

    try:
        resp = client.chat.completions.create(
            model="grok-code-fast-1",  # швидка модель для тексту та коду
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=8192,
            timeout=600
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        st.warning(f"Помилка рерайту: {str(e)}. Залишаємо оригінал.")
        return original_html

st.title("🌐 Rewriter + DUPLICATOR — Рерайт тексту + Клонування")

with st.expander("ℹ️ Як використовувати", expanded=True):
    st.markdown("""
    1. Введи xAI API Key  
    2. Завантаж ZIP/RAR архів(и) сайту  
    3. Обери кількість копій і доменну зону  
    4. Натисни кнопку — отримай архіви з переписаним текстом і новими доменами
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
    copies_count = st.number_input("Копій на архів:", min_value=1, max_value=20, value=5)

if uploaded_files and api_key:
    if st.button("🚀 Створити 5 варіантів з рерайтом", type="primary"):
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=600)

        temp_input = tempfile.mkdtemp()
        temp_rewritten = tempfile.mkdtemp()
        temp_clones = tempfile.mkdtemp()

        progress = st.progress(0)
        status = st.empty()

        # 1. Збереження архівів
        status.text("Зберігаємо архіви...")
        archive_paths = []
        for i, f in enumerate(uploaded_files):
            path = os.path.join(temp_input, f.name)
            with open(path, 'wb') as out:
                out.write(f.getbuffer())
            archive_paths.append(path)
            progress.progress((i+1)/len(uploaded_files) * 0.1)

        # 2. Розпаковка та рерайт
        status.text("Розпаковуємо та рерайтимо текст...")
        all_rewritten_dirs = []
        for arch_idx, arch in enumerate(archive_paths):
            extract_dir = os.path.join(temp_rewritten, f"arch_{arch_idx}")
            os.makedirs(extract_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(arch, 'r') as z:
                    z.extractall(extract_dir)
            except:
                st.warning(f"Не вдалося розпакувати {os.path.basename(arch)}")
                continue

            html_files = [os.path.join(root, f) for root, _, fs in os.walk(extract_dir) for f in fs if f.lower().endswith('.html')]

            lang = get_site_language(html_files)
            st.info(f"Мова архіву {os.path.basename(arch)}: {lang}")

            for html in html_files:
                with open(html, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                new_content = rewrite_content(client, content, lang)
                with open(html, 'w', encoding='utf-8') as f:
                    f.write(new_content)

            all_rewritten_dirs.append(extract_dir)
            progress.progress(0.1 + (arch_idx+1)/len(archive_paths) * 0.4)

        # 3. Клонування (створення 5 варіантів)
        status.text("Створюємо 5 копій з новими доменами...")
        master_zip_path = os.path.join(temp_clones, "duplicates.zip")
        with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as master_zip:
            for var_num in range(1, 6):
                for dir_idx, rewritten_dir in enumerate(all_rewritten_dirs):
                    new_dir = os.path.join(temp_clones, f"var_{var_num}_arch_{dir_idx}")
                    shutil.copytree(rewritten_dir, new_dir, dirs_exist_ok=True)
                    # Тут можна додати заміну доменів (наприклад, функцію replace_domain_in_dir)
                    # Приклад: replace_domain_in_dir(new_dir, "old.com", f"newdomain{var_num}{domain_zone}")

                    for root, _, files in os.walk(new_dir):
                        for file in files:
                            full = os.path.join(root, file)
                            arc = os.path.relpath(full, temp_clones)
                            master_zip.write(full, arc)

        st.session_state.result = {'success': True, 'master_archive_path': master_zip_path}
        st.session_state.processed = True
        st.rerun()

else:
    st.warning("Введи ключ і завантаж архіви")

if st.session_state.processed and st.session_state.result:
    st.success("Готово! 5 варіантів створено.")
    with open(st.session_state.result['master_archive_path'], 'rb') as f:
        data = f.read()
    st.download_button(
        label="⬇️ Скачати головний архів (всі 5 варіантів з рерайтом)",
        data=data,
        file_name="rewritten_duplicates.zip",
        mime="application/zip"
    )

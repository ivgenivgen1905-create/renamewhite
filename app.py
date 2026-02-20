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

# Фіксуємо seed для langdetect, щоб результати були відтворювані
DetectorFactory.seed = 0

st.set_page_config(
    page_title="Rewriter + DUPLICATOR - Рерайт + Клонування сайтів",
    page_icon="🌐🔄",
    layout="wide"
)

# Ініціалізація session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'result' not in st.session_state:
    st.session_state.result = None

def detect_site_language(html_content: str) -> str:
    """Визначає мову сторінки за текстом"""
    try:
        # Беремо тільки текст без тегів
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 50:
            return "unknown"
        lang = detect(text)
        # Мапимо на зрозумілі назви
        lang_map = {
            'uk': 'Українська',
            'ru': 'Російська',
            'en': 'Англійська',
            'fr': 'Французька',
            'de': 'Німецька',
            'pl': 'Польська',
            # додай інші за потребою
        }
        return lang_map.get(lang, lang.upper())
    except LangDetectException:
        return "unknown"

def get_dominant_language(html_files: list) -> str:
    """Визначає домінуючу мову сайту по всіх HTML"""
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
        return "Українська"  # дефолт
    
    # Найпоширеніша мова
    most_common = Counter(languages).most_common(1)
    return most_common[0][0] if most_common else "Українська"

def rewrite_html_with_grok(client, html_content: str, language: str, business_name: str) -> str:
    """Рерайт однієї сторінки через Grok"""
    prompt = f"""
Перепиши весь видимий текст на сторінці на мові '{language}' — зроби унікальним, природним, привабливим.
Зберігай 100% HTML-структуру, теги, атрибути, скрипти, стилі, посилання, картинки — нічого не видаляй і не додавай.
Для контактів (адреса, телефон, локація) — заміни на випадкові правдоподібні дані на основі бізнесу '{business_name}' 
(адреса в Україні, номер телефону +380...).
Повертай ТІЛЬКИ чистий HTML-код, без жодних пояснень чи маркдауну.
Оригінальний HTML:
{html_content}
"""

    try:
        resp = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",  # швидка модель
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
        st.error(f"Помилка рерайту сторінки: {str(e)}")
        return html_content  # повертаємо оригінал, якщо помилка

# ────────────────────────────────────────────────
# Основний інтерфейс (збережено з DUPLICATOR)
# ────────────────────────────────────────────────

st.title("🌐 Rewriter + DUPLICATOR — Рерайт + Клонування сайтів")

with st.expander("ℹ️ Як використовувати", expanded=True):
    st.markdown("""
    1. Завантажте ZIP/RAR архів(и) з сайтом
    2. Вкажіть API-ключ xAI та назву бізнесу (для випадкових контактів)
    3. Оберіть кількість копій і доменну зону
    4. Натисніть "Створити копії з рерайтом"
    """)

api_key = st.text_input("xAI API Key", type="password")
business_name = st.text_input("Назва бізнесу (для генерації контактів)")

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

if uploaded_files and api_key and business_name:
    if st.button("🚀 Створити копії з рерайтом", type="primary"):
        if not api_key.startswith("xai-"):
            st.error("Невірний формат API-ключа. Повинен починатися з 'xai-'")
            st.stop()

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=300)

        temp_input = tempfile.mkdtemp()
        temp_output = tempfile.mkdtemp()
        temp_rewritten = tempfile.mkdtemp()

        progress = st.progress(0)
        status = st.empty()

        # Крок 1: збереження файлів
        status.text("Зберігаємо архіви...")
        archive_paths = []
        for i, f in enumerate(uploaded_files):
            path = os.path.join(temp_input, f.name)
            with open(path, 'wb') as out:
                out.write(f.getbuffer())
            archive_paths.append(path)
            progress.progress((i+1)/len(uploaded_files) * 0.1)

        # Крок 2: розпаковка та визначення мови
        status.text("Розпаковуємо та визначаємо мову сайту...")
        all_html_files = []
        for arch in archive_paths:
            extract_dir = os.path.join(temp_rewritten, os.path.basename(arch).replace('.zip','').replace('.rar',''))
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(arch, 'r') as z:  # можна додати rar підтримку через rarfile
                z.extractall(extract_dir)
            htmls = [os.path.join(root, f) for root, _, fs in os.walk(extract_dir) for f in fs if f.lower().endswith('.html')]
            all_html_files.extend(htmls)

        if all_html_files:
            detected_lang = get_dominant_language(all_html_files)
            st.success(f"Визначено мову сайту: **{detected_lang}**")
        else:
            detected_lang = "Українська"
            st.warning("Мову не вдалося визначити → використовуємо Українську")

        # Крок 3: рерайт тексту
        status.text("Рерайт тексту на виявленій мові...")
        rewritten_count = 0
        for html_path in all_html_files:
            try:
                with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                new_content = rewrite_html_with_grok(client, content, detected_lang, business_name)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                rewritten_count += 1
            except:
                pass

        st.info(f"Переписано {rewritten_count} сторінок")

        # Крок 4: клонування з заміною доменів (тут треба твій BatchProcessor)
        # Якщо у тебе є utils.batch_processor — імпортуй і використовуй
        # Для прикладу — просто імітуємо (заміни на свій код)
        status.text("Створюємо копії з новими доменами...")
        # processor = BatchProcessor()
        # result = processor.process_multiple_archives(
        #     archives=[temp_rewritten],  # вже з рерайтом
        #     copies_count=copies_count,
        #     domain_zone=domain_zone,
        #     output_dir=temp_output
        # )

        # Тимчасово — просто копіюємо як приклад
        result = {
            'success': True,
            'master_archive_path': os.path.join(temp_output, "master.zip")
        }

        # Крок 5: створення головного архіву (тут твій код)
        # ...

        st.session_state.result = result
        st.session_state.processed = True
        st.rerun()

else:
    st.warning("Заповніть усі поля: API-ключ, бізнес, архіви")

if st.session_state.processed and st.session_state.result:
    st.success("Готово!")
    # Тут кнопка завантаження з result['master_archive_path']

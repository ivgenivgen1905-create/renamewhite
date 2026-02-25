import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
import re
import random
import string
from openai import OpenAI
from langdetect import detect, LangDetectException
from collections import Counter

st.set_page_config(
    page_title="Rewriter + DUPLICATOR — Рерайт тексту + Клонування",
    page_icon="🌐🔄",
    layout="wide"
)

# Session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'result' not in st.session_state:
    st.session_state.result = None

def generate_unique_site_names(theme, num=5):
    """Генерація унікальних назв сайту на основі теми"""
    themes = {
        'здоров я': ['Vital', 'Health', 'Well', 'Pure', 'Balance', 'Life', 'Energy', 'Gesund'],
        'спорт': ['Sport', 'Fit', 'Active', 'Power', 'Gym', 'Run', 'Athlet', 'Train'],
        'краса': ['Beauty', 'Glow', 'Shine', 'Elegant', 'Charm', 'Style', 'Lux', 'Fashion'],
        'їжа': ['Food', 'Taste', 'Delicious', 'Gourmet', 'Kitchen', 'Recipe', 'Eat', 'Flavor'],
    }
    base_words = themes.get(theme.lower(), ['Site', 'Web', 'Net', 'Pro', 'Hub'])
    names = []
    for _ in range(num):
        word = random.choice(base_words)
        suffix = ''.join(random.choice(string.ascii_lowercase) for _ in range(random.randint(3, 6)))
        name = word + suffix.capitalize()
        names.append(name)
    return names

def detect_language(text: str) -> str:
    text_lower = text.lower()
    if len(text.strip()) < 50:
        return "de"

    # Ультра-посилена евристика для індонезійської
    indonesian_strong = ["gizi", "ahli gizi", "pola makan", "sehari-hari", "seimbang", "kesehatan", "suplemen", "vitamin", "makanan", "diet", "hidup sehat"]
    indo_strong_count = sum(1 for word in indonesian_strong if word in text_lower)
    indonesian_weak = ["dalam", "untuk", "dan", "ini", "sangat", "penting", "pendekatan", "berbasis", "alami", "modern", "memandang", "sebagai", "bagian", "gaya hidup", "keseimbangan", "keteraturan", "pemilihan", "komponen", "sadar"]
    indo_weak_count = sum(1 for word in indonesian_weak if word in text_lower)
    if indo_strong_count >= 1 or (indo_strong_count + indo_weak_count >= 5):
        return "id"

    # Німецька
    if re.search(r'[äöüÄÖÜß]', text) or any(w in text_lower for w in ["gesund", "ernährung", "wohlbefinden", "energie", "frauen", "männer"]):
        return "de"

    # Румунська
    if re.search(r'[ăĂâÂîÎșȘțȚ]', text) or any(w in text_lower for w in ["cum", "să", "alegi", "vitaminele", "potrivite", "sfaturile", "nutriționistului", "pentru", "dietă", "echilibrată", "sănătate"]):
        return "ro"

    # Українська
    if any(w in text_lower for w in ["здоров", "здоров'я", "енергія", "жінки", "чоловіки", "життя", "баланс"]):
        return "uk"

    # Російська
    if any(w in text_lower for w in ["здоровье", "питание", "энергия", "женщины", "мужчины", "жизнь"]):
        return "ru"

    # Англійська
    if any(w in text_lower for w in ["health", "nutrition", "energy", "women", "men", "life"]):
        return "en"

    # Французька
    if any(w in text_lower for w in ["santé", "nutrition", "énergie", "femmes", "hommes", "vie"]):
        return "fr"

    # Іспанська
    if any(w in text_lower for w in ["salud", "nutrición", "energía", "mujeres", "hombres", "vida"]):
        return "es"

    # Італійська
    if any(w in text_lower for w in ["salute", "nutrizione", "energia", "donne", "uomini", "vita"]):
        return "it"

    # Польська
    if any(w in text_lower for w in ["zdrowie", "odżywianie", "energia", "kobiety", "mężczyźni", "życie"]):
        return "pl"

    # Нідерландська
    if any(w in text_lower for w in ["gezondheid", "voeding", "energie", "vrouwen", "mannen", "leven"]):
        return "nl"

    # Шведська
    if any(w in text_lower for w in ["hälsa", "näring", "energi", "kvinnor", "män", "liv"]):
        return "sv"

    # Португальська
    if any(w in text_lower for w in ["saúde", "nutrição", "energia", "mulheres", "homens", "vida"]):
        return "pt"

    # Словенська
    if any(w in text_lower for w in ["zdravje", "prehrana", "energija", "ženske", "moški", "življenje"]):
        return "sl"

    # Словацька
    if any(w in text_lower for w in ["zdravie", "výživa", "energia", "ženy", "muži", "život"]):
        return "sk"

    # Малайська
    if any(w in text_lower for w in ["kesihatan", "pemakanan", "tenaga", "wanita", "lelaki", "hidup"]):
        return "ms"

    # Індійська (хінді)
    if re.search(r'[हिन्दी]', text) or any(w in text_lower for w in ["स्वास्थ्य", "पोषण", "ऊर्जा", "महिलाएं", "पुरुष", "जीवन"]):
        return "hi"

    # Чеська
    if any(w in text_lower for w in ["zdraví", "výživa", "energie", "ženy", "muži", "život"]):
        return "cs"

    # Угорська
    if any(w in text_lower for w in ["egészség", "táplálkozás", "energia", "nők", "férfiak", "élet"]):
        return "hu"

    # Сербська
    if any(w in text_lower for w in ["здравље", "исхрана", "енергија", "жене", "мушкарци", "живот"]):
        return "sr"

    # Грецька
    if re.search(r'[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]', text) or any(w in text_lower for w in ["υγεία", "διατροφή", "ενέργεια", "γυναίκες", "άνδρες", "ζωή"]):
        return "el"

    # Турецька
    if any(w in text_lower for w in ["sağlık", "beslenme", "enerji", "kadınlar", "erkekler", "hayat"]):
        return "tr"

    # Арабська
    if re.search(r'[عربي]', text) or any(w in text_lower for w in ["صحة", "تغذية", "طاقة", "نساء", "رجال", "حياة"]):
        return "ar"

    try:
        lang = detect(text)
        if lang in ['id', 'ms']:
            return "id"
        return lang
    except LangDetectException:
        return "de"

def get_site_language(html_files: list) -> str:
    langs = []
    for path in html_files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            text = re.sub(r'<[^>]+>', ' ', content)[:15000]
            lang = detect_language(text)
            langs.append(lang)
        except:
            pass
    
    if not langs:
        return "de"

    most_common = Counter(langs).most_common(1)[0][0]
    lang_map = {
        'de': 'Німецька',
        'uk': 'Українська',
        'ru': 'Російська',
        'en': 'Англійська',
        'fr': 'Французька',
        'es': 'Іспанська',
        'it': 'Італійська',
        'pl': 'Польська',
        'nl': 'Нідерландська',
        'sv': 'Шведська',
        'pt': 'Португальська',
        'ro': 'Румунська',
        'sl': 'Словенська',
        'sk': 'Словацька',
        'id': 'Індонезійська',
        'ms': 'Малайська',
        'hi': 'Індійська (хінді)',
        'cs': 'Чеська',
        'hu': 'Угорська',
        'sr': 'Сербська',
        'el': 'Грецька',
        'tr': 'Турецька',
        'ar': 'Арабська',
    }
    return lang_map.get(most_common, "Німецька")

lang_to_countries = {
    'Німецька': ['Німеччина', 'Австрія', 'Швейцарія'],
    'Українська': ['Україна'],
    'Російська': ['Росія', 'Білорусь', 'Казахстан'],
    'Англійська': ['США', 'Великобританія', 'Австралія', 'Канада', 'Ірландія'],
    'Французька': ['Франція', 'Канада', 'Бельгія', 'Швейцарія'],
    'Іспанська': ['Іспанія', 'Мексика', 'Аргентина', 'Колумбія'],
    'Італійська': ['Італія', 'Швейцарія'],
    'Польська': ['Польща'],
    'Нідерландська': ['Нідерланди', 'Бельгія'],
    'Шведська': ['Швеція', 'Фінляндія'],
    'Португальська': ['Португалія', 'Бразилія'],
    'Румунська': ['Румунія', 'Молдова'],
    'Словенська': ['Словенія'],
    'Словацька': ['Словаччина'],
    'Індонезійська': ['Індонезія'],
    'Малайська': ['Малайзія', 'Бруней', 'Сінгапур'],
    'Індійська (хінді)': ['Індія'],
    'Чеська': ['Чехія'],
    'Угорська': ['Угорщина'],
    'Сербська': ['Сербія', 'Чорногорія', 'Боснія і Герцеговина'],
    'Грецька': ['Греція', 'Кіпр'],
    'Турецька': ['Туреччина'],
    'Арабська': ['Єгипет', 'Саудівська Аравія', 'Об’єднані Арабські Емірати', 'Марокко', 'Алжир'],
}

lang_to_phone = {
    'Німецька': '+49',
    'Українська': '+380',
    'Російська': '+7',
    'Англійська': '+44',
    'Французька': '+33',
    'Іспанська': '+34',
    'Італійська': '+39',
    'Польська': '+48',
    'Нідерландська': '+31',
    'Шведська': '+46',
    'Португальська': '+351',
    'Румунська': '+40',
    'Словенська': '+386',
    'Словацька': '+421',
    'Індонезійська': '+62',
    'Малайська': '+60',
    'Індійська (хінді)': '+91',
    'Чеська': '+420',
    'Угорська': '+36',
    'Сербська': '+381',
    'Грецька': '+30',
    'Турецька': '+90',
    'Арабська': '+20',
}

def rewrite_content(client, original_html: str, language: str, new_site_name: str) -> str:
    if language not in lang_to_countries:
        st.error(f"Мова '{language}' не підтримується.")
        return original_html

    country = random.choice(lang_to_countries[language])
    phone_prefix = lang_to_phone.get(language, '+1')

    prompt = f"""
ТІЛЬКИ рефразуй видимий текст на мові '{language}' — зроби його унікальним, природним, привабливим.
ЗАБОРОНЕНО будь-які зміни крім тексту:
- НЕ змінювати теги, атрибути, класи, id, name, value, placeholder, action, method, onclick, src, href
- НЕ ламати форми, input, button, select, textarea, скрипти, стилі, посилання, зображення
- НЕ додавати/видаляти елементи
- НЕ змінювати JS-код, події, структуру
Замінюй ТІЛЬКИ чистий текст всередині тегів (h1-h6, p, li, span, div з текстом, label, option тощо).
Заміни назву сайту на '{new_site_name}' всюди, де вона згадується в тексті.
Контакти (адреса, телефон) — заміни на випадкові правдоподібні (адреса в {country}, номер телефону {phone_prefix}...).
Якщо контактів не було — не додавай їх.
Повертай ТІЛЬКИ повний HTML/PHP з заміненим текстом, без пояснень.
Оригінал:
{original_html}
"""

    try:
        resp = client.chat.completions.create(
            model="grok-code-fast-1",
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
    2. Введи тему сайту (для генерації назв, напр. 'здоров я')
    3. Завантаж ZIP/RAR архів(и) сайту  
    4. Обери кількість копій і доменну зону  
    5. Натисни кнопку — отримай архів з 5 унікальними варіантами (кожен з рерайтом, новою назвою і доменом)
    """)

api_key = st.text_input("xAI API Key", type="password")
theme = st.text_input("Тема сайту (для генерації назв)", value="здоров я")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_files = st.file_uploader(
        "Архіви сайтів (ZIP/RAR)",
        type=['zip', 'rar'],
        accept_multiple_files=True
    )

with col2:
    domain_zone = st.radio("Доменна зона:", ['.com', '.info'], horizontal=True)
    copies_count = st.number_input("Копій на архів:", min_value=1, max_value=5, value=5)

if uploaded_files and api_key and theme:
    if st.button("🚀 Створити 5 унікальних копій з рерайтом", type="primary"):
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

        # Генеруємо унікальні назви
        unique_names = generate_unique_site_names(theme, copies_count * len(archive_paths))
        name_index = 0

        # 2. Рерайт і варіанти
        status.text("Рерайт і створення унікальних варіантів...")
        master_zip_path = os.path.join(temp_clones, "duplicates.zip")
        with zipfile.ZipFile(master_zip_path, 'w', zipfile.ZIP_DEFLATED) as master_zip:
            for var_num in range(1, copies_count + 1):
                status.text(f"Варіант {var_num} з {copies_count}...")
                for arch_idx, arch in enumerate(archive_paths):
                    extract_dir = os.path.join(temp_rewritten, f"var_{var_num}_arch_{arch_idx}")
                    os.makedirs(extract_dir, exist_ok=True)
                    try:
                        with zipfile.ZipFile(arch, 'r') as z:
                            z.extractall(extract_dir)
                    except:
                        st.warning(f"Не вдалося розпакувати {os.path.basename(arch)}")
                        continue

                    # Фільтруємо .html, .htm та .php файли для рерайту
                    text_files = [os.path.join(root, f) for root, _, fs in os.walk(extract_dir) for f in fs if f.lower().endswith(('.html', '.htm', '.php'))]

                    lang = get_site_language(text_files)
                    st.info(f"Мова для варіанта {var_num} архіву {os.path.basename(arch)}: {lang}")

                    new_site_name = unique_names[name_index]
                    name_index += 1

                    rewritten_count = 0
                    for file_path in text_files:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        new_content = rewrite_content(client, content, lang, new_site_name)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        rewritten_count += 1

                    # Додаємо в головний архів ВСІ файли (включаючи не-html/php)
                    for root, _, files in os.walk(extract_dir):
                        for file in files:
                            full = os.path.join(root, file)
                            arc = os.path.relpath(full, temp_rewritten)
                            master_zip.write(full, arc)

                    st.info(f"Варіант {var_num} архіву {arch_idx} готовий: {rewritten_count} файлів переписано, нова назва {new_site_name}")

                    progress.progress(0.1 + (var_num * (arch_idx+1)) / (copies_count * len(archive_paths)) * 0.9)

        st.session_state.result = {'success': True, 'master_archive_path': master_zip_path}
        st.session_state.processed = True
        st.rerun()

else:
    st.warning("Введи ключ, тему і завантаж архіви")

if st.session_state.processed and st.session_state.result:
    st.success("Готово! 5 унікальних варіантів з рерайтом і назвами.")
    with open(st.session_state.result['master_archive_path'], 'rb') as f:
        data = f.read()
    st.download_button(
        label="⬇️ Скачати головний архів (всі 5 варіантів)",
        data=data,
        file_name="unique_rewritten_duplicates.zip",
        mime="application/zip"
    )

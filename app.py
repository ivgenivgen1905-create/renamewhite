import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
from xai_sdk import Client

st.title("Rewriter: 5 варіантів сайту з рерайтом тексту")

api_key = st.text_input("Введи xAI API Key", type="password")
business_name = st.text_input("Назва бізнесу (для випадкових контактів)")
language = st.selectbox("Мова рерайту", options=["Українська", "Англійська", "Російська", "Французька", "Німецька"])
uploaded_zip = st.file_uploader("Завантаж ZIP-архів сайту", type="zip")

if uploaded_zip and api_key and business_name and language:
    if st.button("Створити 5 варіантів рерайту"):
        with st.spinner("Розпаковуємо архів, рерайтимо сторінки через Grok..."):
            temp_dir = tempfile.mkdtemp()
            extract_dir = os.path.join(temp_dir, "orig")
            os.makedirs(extract_dir, exist_ok=True)

            # Розпаковуємо ZIP
            with zipfile.ZipFile(uploaded_zip, "r") as z:
                z.extractall(extract_dir)

            # Знаходимо всі .html
            html_files = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.lower().endswith(".html"):
                        html_files.append(os.path.join(root, file))

            if not html_files:
                st.error("У ZIP немає HTML-файлів.")
                shutil.rmtree(temp_dir)
            else:
                try:
                    client = Client(api_key=api_key)
                except Exception as e:
                    st.error(f"Помилка з API-ключем: {str(e)}. Перевір ключ і баланс.")
                    shutil.rmtree(temp_dir)
                    return

                for var_num in range(1, 6):
                    st.write(f"Генеруємо варіант {var_num} з 5...")

                    var_dir = os.path.join(temp_dir, f"var_{var_num}")
                    shutil.copytree(extract_dir, var_dir, dirs_exist_ok=True)

                    for html_file in html_files:
                        with open(html_file, "r", encoding="utf-8") as f:
                            orig_html = f.read()

                        prompt = f"""
Перепиши весь видимий текст на сторінці: зроби унікальним, природним, привабливим на мові '{language}'.
Зберігай 100% HTML-структуру, теги, атрибути, скрипти, стилі, посилання, картинки — НЕ чіпай їх.
Для контактів (адреса, телефон, локація) — придумай випадкові, але правдоподібні дані на основі бізнесу '{business_name}' (використовуй свої знання: адреса в реальному місті, номер телефону в форматі країни).
Заміни існуючі контакти на нові випадкові.
Повертай ТІЛЬКИ чистий HTML-код, без пояснень.
Оригінальний HTML:
{orig_html}
"""

                        resp = client.chat.completions.create(
                            model="grok-4",
                            messages=[
                                {"role": "system", "content": "Ти експерт з рерайту веб-контенту на обраній мові з генерацією випадкових контактів."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7 + (var_num * 0.05),
                            max_tokens=16384
                        )

                        new_html = resp.choices[0].message.content.strip()

                        new_path = html_file.replace(extract_dir, var_dir)
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        with open(new_path, "w", encoding="utf-8") as f:
                            f.write(new_html)

                    # Створюємо ZIP у пам'яті
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for rt, _, fs in os.walk(var_dir):
                            for fl in fs:
                                full = os.path.join(rt, fl)
                                rel = os.path.relpath(full, var_dir)
                                zf.write(full, rel)

                    zip_buf.seek(0)

                    st.download_button(
                        label=f"Завантажити варіант {var_num}",
                        data=zip_buf,
                        file_name=f"rewritten_var_{var_num}.zip",
                        mime="application/zip",
                        key=f"btn_{var_num}"
                    )

                shutil.rmtree(temp_dir)
                st.success("Готово! Завантажуй варіанти вище ↓")

else:
    st.info("Заповни всі поля, щоб почати.")
    if not api_key:
        st.warning("Потрібен xAI API Key → https://console.x.ai")
    if not business_name:
        st.warning("Вкажи назву бізнесу для випадкових контактів.")
    if not language:
        st.warning("Обери мову рерайту.")
    if not uploaded_zip:
        st.warning("Завантаж ZIP з сайтом (статичний, з HTML).")

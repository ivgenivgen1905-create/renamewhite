import streamlit as st
import zipfile
import tempfile
import os
import shutil
import io
from openai import OpenAI  # ← зміна тут!

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

            with zipfile.ZipFile(uploaded_zip, "r") as z:
                z.extractall(extract_dir)

            html_files = [os.path.join(root, f) for root, _, files in os.walk(extract_dir) for f in files if f.lower().endswith('.html')]

            if not html_files:
                st.error("У ZIP немає HTML-файлів.")
                shutil.rmtree(temp_dir)
            else:
                try:
                    client = OpenAI(
                        api_key=api_key,
                        base_url="https://api.x.ai/v1"  # ← ключовий рядок!
                    )
                except Exception as e:
                    st.error(f"Помилка ініціалізації клієнта: {str(e)}. Перевір ключ і баланс.")
                    shutil.rmtree(temp_dir)
                    st.stop()

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
Для контактів (адреса, телефон, локація) — придумай випадкові, але правдоподібні дані на основі бізнесу '{business_name}' (використовуй свої знання: адреса в реальному місті України, номер телефону в форматі +380...).
Заміни існуючі контакти на нові випадкові.
Повертай ТІЛЬКИ чистий HTML-код, без пояснень.
Оригінальний HTML:
{orig_html}
"""

                        try:
                            resp = client.chat.completions.create(
                                model="grok-4",  # або "grok-beta", "grok-3" — перевір актуальні в https://console.x.ai/models
                                messages=[
                                    {"role": "system", "content": "Ти експерт з рерайту веб-контенту на обраній мові з генерацією випадкових контактів."},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.7 + (var_num * 0.05),
                                max_tokens=16384
                            )
                            new_html = resp.choices[0].message.content.strip()
                        except Exception as e:
                            st.error(f"Помилка під час рерайту: {str(e)}. Спробуй менший сайт або перевір баланс.")
                            continue

                        new_path = html_file.replace(extract_dir, var_dir)
                        os.makedirs(os.path.dirname(new_path), exist_ok=True)
                        with open(new_path, "w", encoding="utf-8") as f:
                            f.write(new_html)

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
        st.warning("Вкажи назву бізнесу.")
    if not language:
        st.warning("Обери мову рерайту.")
    if not uploaded_zip:
        st.warning("Завантаж ZIP з сайтом.")

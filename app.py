import streamlit as st
import pandas as pd
import os
import json
import requests
import re
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Cargar variables de entorno
load_dotenv()

# ==========================================
# 1. CLASES DEL SISTEMA (Backend)
# ==========================================

class QwenGenerator:
    def __init__(self):
        # OpenRouter usa la interfaz de OpenAI pero con su propia URL
        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        # Modelo Qwen 2.5 72B (gratuito/barato y excelente en español)
        self.model = "qwen/qwen-2.5-72b-instruct"

    def generar(self, empresa, tipo):
        prompts = {
            "experiencia": f"Escribe un párrafo de 150 palabras en primera persona del plural ('hemos probado', 'nuestro equipo') simulando una verificación real del teléfono {empresa['telefono_900']} de {empresa['nombre']}. Menciona el tiempo de espera ({empresa['tiempo_espera_min']} min), la amabilidad del operador y un consejo específico para navegar su menú de voz ({empresa['menu_voz_ruta']}). Tono: profesional, útil, cercano y de mucha confianza. Español de España.",
            "consejos": f"Escribe 3 consejos prácticos, numerados y específicos para reclamar a una empresa del sector '{empresa['sector']}' como {empresa['nombre']}. Incluye menciones reales a la OMIC, Consumo o libros de reclamaciones. Tono: empoderador para el consumidor. Español de España.",
            "comparativa": f"Compara brevemente a {empresa['nombre']} con {empresa['sector_relacionado_1']} y {empresa['sector_relacionado_2']} en cuanto a facilidad de contacto. Sé objetivo y breve (máx 100 palabras). Español de España."
        }
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un redactor experto en SEO y consumo en España. Escribe texto 100% original, natural, sin clichés de IA. Evita frases como 'En conclusión', 'Es importante destacar', 'Sumérgete'."},
                    {"role": "user", "content": prompts[tipo]}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Error OpenRouter: {str(e)}]"

class SmartScraper:
    def extraer(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            tel = re.search(r'(900[\s-]?\d{3}[\s-]?\d{3})', text)
            horario = re.search(r'(\d{1,2}:\d{2}\s*(?:a|de|hasta|-)\s*\d{1,2}:\d{2})', text, re.IGNORECASE)
            
            return {
                'telefono': tel.group(1).replace(' ', '').replace('-', '') if tel else "No encontrado",
                'horario': horario.group(1) if horario else "Consultar web"
            }
        except:
            return {'telefono': "Error", 'horario': "Error"}

class ValidadorAdSense:
    def validar(self, texto, empresa):
        errores = []
        if len(texto.split()) < 500:
            errores.append("❌ El texto tiene menos de 500 palabras (Riesgo Thin Content).")
        if "hemos" not in texto.lower() and "probado" not in texto.lower():
            errores.append("❌ Falta lenguaje de experiencia en primera persona (E-E-A-T).")
        if empresa['nombre'].lower() not in texto.lower():
            errores.append("❌ El nombre de la empresa no aparece en el texto.")
        
        puntuacion = 100 - (len(errores) * 30)
        return {"aprobado": len(errores) == 0, "errores": errores, "puntuacion": max(0, puntuacion)}

class WPPublisher:
    def publicar(self, titulo, contenido):
        url = f"{os.getenv('WP_URL').rstrip('/')}/wp-json/wp/v2/posts"
        user = os.getenv('WP_USER')
        pwd = os.getenv('WP_APP_PASSWORD')
        
        payload = {
            "title": titulo,
            "content": contenido,
            "status": "draft"
        }
        try:
            response = requests.post(url, auth=(user, pwd), json=payload)
            if response.status_code == 201:
                return {"success": True, "url": response.json()['link']}
            return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

# ==========================================
# 2. INTERFAZ DE USUARIO (Frontend Streamlit)
# ==========================================

st.set_page_config(page_title="Gestor Telefonos Gratuitos", page_icon="📞", layout="wide")
st.title("📞 Panel de Control: telefonos-gratuitos.com")
st.markdown("Automatización SEO + AdSense + Qwen AI + WordPress")

# --- Cargar Base de Datos ---
CSV_PATH = "data/empresas.csv"
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
else:
    df = pd.DataFrame(columns=["nombre", "sector", "telefono_900", "web_oficial", "tiempo_espera_min", "menu_voz_ruta", "sector_relacionado_1", "sector_relacionado_2"])

# --- Sidebar ---
st.sidebar.header("⚙️ Configuración")
st.sidebar.info("Las claves se cargan desde el archivo `.env`")
if not os.getenv("OPENROUTER_API_KEY"):
    st.sidebar.error("⚠️ Falta OPENROUTER_API_KEY en el archivo .env")
else:
    st.sidebar.success("✅ API Key de OpenRouter configurada")

# --- Tabs Principales ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 1. Base de Datos", "🕷️ 2. Scraping", "🤖 3. Generar Artículo", "🚀 4. Publicar"])

# TAB 1: BASE DE DATOS
with tab1:
    st.header("Gestión de Empresas")
    st.markdown("Edita la tabla directamente como si fuera Excel. Los cambios se guardan al pulsar el botón.")
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 Guardar Cambios en CSV", type="primary"):
        edited_df.to_csv(CSV_PATH, index=False)
        st.success("✅ Base de datos actualizada correctamente.")
        df = edited_df

# TAB 2: SCRAPING
with tab2:
    st.header("🕷️ Extracción Inteligente de Datos")
    url = st.text_input("Pega la URL de la web oficial de la empresa (ej: https://www.orange.es):")
    
    if st.button("🔍 Analizar Web"):
        if url:
            with st.spinner("Rastreando la web en busca del 900 y horarios..."):
                scraper = SmartScraper()
                resultado = scraper.extraer(url)
                
                col1, col2 = st.columns(2)
                col1.metric("Teléfono 900 Detectado", resultado['telefono'])
                col2.metric("Horario Detectado", resultado['horario'])
                
                if resultado['telefono'] != "No encontrado" and resultado['telefono'] != "Error":
                    st.success("¡Datos extraídos con éxito! Cópialos y pégalos en la pestaña 'Base de Datos'.")

# TAB 3: GENERADOR CON IA
with tab3:
    st.header("🤖 Generador de Artículos Premium (Anti-AdSense)")
    
    if df.empty or df['nombre'].dropna().empty:
        st.warning("Primero añade empresas en la pestaña 'Base de Datos'.")
    else:
        empresa_seleccionada = st.selectbox("Selecciona una empresa para generar su artículo:", df['nombre'].dropna().tolist())
        datos_empresa = df[df['nombre'] == empresa_seleccionada].iloc[0].to_dict()
        
        if st.button("✨ Generar Contenido con Qwen (OpenRouter)", type="primary"):
            with st.spinner("Qwen está redactando contenido único, humano y optimizado..."):
                ai = QwenGenerator()
                
                exp = ai.generar(datos_empresa, "experiencia")
                consejos = ai.generar(datos_empresa, "consejos")
                comp = ai.generar(datos_empresa, "comparativa")
                
                st.session_state['articulo_exp'] = exp
                st.session_state['articulo_consejos'] = consejos
                st.session_state['articulo_comp'] = comp
                st.session_state['empresa_actual'] = datos_empresa
                
                st.success("✅ Contenido generado. Revisa las secciones abajo y pasa a la pestaña 'Publicar'.")
                
                with st.expander("👁️ Vista Previa: Nuestra Experiencia"):
                    st.markdown(exp)
                with st.expander("👁️ Vista Previa: Consejos de Reclamación"):
                    st.markdown(consejos)

# TAB 4: PUBLICAR Y VALIDAR
with tab4:
    st.header("🚀 Validación Final y Publicación en WordPress")
    
    if 'empresa_actual' not in st.session_state:
        st.info("Primero genera un artículo en la pestaña anterior.")
    else:
        emp = st.session_state['empresa_actual']
        exp = st.session_state.get('articulo_exp', '')
        consejos = st.session_state.get('articulo_consejos', '')
        
        articulo_final = f"""# Teléfono Gratuito de {emp['nombre']} {datetime.now().year} - Atención al Cliente Gratis

**Última verificación:** {datetime.now().strftime("%d de %B de %Y")} ✅  
**Autor:** Equipo Editorial de telefonos-gratuitos.com

---

## 📞 El Teléfono Gratuito
El teléfono de atención al cliente gratuito de **{emp['nombre']}** es el **{emp['telefono_900']}**. Es totalmente gratis desde fijo y móvil en España.

| Dato | Información |
|------|-------------|
| **Teléfono** | **{emp['telefono_900']}** |
| **Horario** | {emp.get('horario_lunes_viernes', 'Consultar web')} |
| **Web Oficial** | [{emp['web_oficial']}]({emp['web_oficial']}) |

---

## 📝 Nuestra Experiencia y Verificación
{exp}

---

## 💡 Consejos para Reclamaciones y Trámites
{consejos}

---

## ⚖️ Comparativa del Sector
{st.session_state.get('articulo_comp', '')}

---

*¿Te ha sido útil? Ayuda a otros a evitar los números de pago compartiendo este artículo.*
"""
        
        st.markdown("### 📝 Vista Previa del Artículo Completo")
        st.markdown(articulo_final)
        
        st.divider()
        
        st.subheader("🛡️ Validación Automática para AdSense y SEO")
        validador = ValidadorAdSense()
        resultado_val = validador.validar(articulo_final, emp)
        
        col1, col2 = st.columns(2)
        col1.metric("Puntuación de Calidad", f"{resultado_val['puntuacion']}/100")
        
        if resultado_val['aprobado']:
            col2.success("✅ El artículo cumple con las normativas de AdSense y SEO.")
        else:
            col2.error("⚠️ El artículo necesita mejoras:\n" + "\n".join(resultado_val['errores']))
        
        st.divider()
        
        if st.button("📤 Publicar como Borrador en WordPress", type="primary", disabled=not resultado_val['aprobado']):
            with st.spinner("Conectando con WordPress..."):
                publisher = WPPublisher()
                titulo = f"Teléfono Gratuito de {emp['nombre']} {datetime.now().year}"
                resultado_wp = publisher.publicar(titulo, articulo_final)
                
                if resultado_wp['success']:
                    st.success(f"🎉 ¡Artículo publicado con éxito! [Haz clic aquí para verlo en WordPress]({resultado_wp['url']})")
                    st.info("Recuerda: Se ha guardado como 'Borrador'. Revísalo y dale a 'Publicar' en tu panel de WordPress.")
                else:
                    st.error(f"Error al publicar: {resultado_wp['error']}")

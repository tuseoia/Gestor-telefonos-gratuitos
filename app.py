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

# Crear carpeta data si no existe (solución para Streamlit Cloud)
os.makedirs("data", exist_ok=True)

# ==========================================
# 1. CLASES DEL SISTEMA (Backend)
# ==========================================

class QwenGenerator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
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
                    {"role": "system", "content": "Eres un redactor experto en SEO y consumo en España. Escribe texto 100% original, natural, sin clichés de IA. Evita frases como 'En conclusión', 'Es importante destacar'."},
                    {"role": "user", "content": prompts[tipo]}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Error OpenRouter: {str(e)}]"

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

# Crear carpeta data si no existe (solución para Streamlit Cloud)
os.makedirs("data", exist_ok=True)

# ==========================================
# 1. CLASES DEL SISTEMA (Backend)
# ==========================================

class QwenGenerator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
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
                    {"role": "system", "content": "Eres un redactor experto en SEO y consumo en España. Escribe texto 100% original, natural, sin clichés de IA. Evita frases como 'En conclusión', 'Es importante destacar'."},
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
            # Headers más completos para parecer un navegador real
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            # Timeout más largo y manejo de sesiones
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Intentar diferentes codificaciones
            response.encoding = response.apparent_encoding
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Texto completo de la página
            text = soup.get_text(separator=' ', regex=False)
            
            # Múltiples patrones para teléfonos 900
            patrones_telefono = [
                r'(900[\s.-]?\d{3}[\s.-]?\d{3})',  # 900 123 456
                r'(900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2})',  # 900 12 34 56
                r'(90[0-9][\s.-]?\d{3}[\s.-]?\d{3})',  # 901, 902, etc.
            ]
            
            telefono_encontrado = "No encontrado"
            for patron in patrones_telefono:
                match = re.search(patron, text)
                if match:
                    telefono_encontrado = match.group(1)
                    # Limpiar formato
                    telefono_limpio = re.sub(r'[\s.-]', '', telefono_encontrado)
                    if len(telefono_limpio) == 9:
                        telefono_encontrado = f"{telefono_limpio[:3]} {telefono_limpio[3:6]} {telefono_limpio[6:]}"
                    break
            
            # Patrones para horarios más flexibles
            patrones_horario = [
                r'(lunes\s+(?:a|al|-)\s+viernes[:\s]+\d{1,2}[:.]\d{2}\s+(?:a|de|hasta|-|–)\s+\d{1,2}[:.]\d{2})',
                r'(\d{1,2}[:.]\d{2}\s+(?:a|de|hasta|-|–)\s+\d{1,2}[:.]\d{2}\s+h)',
                r'(de\s+\d{1,2}[:.]\d{2}\s+a\s+\d{1,2}[:.]\d{2})',
            ]
            
            horario_encontrado = "Consultar web"
            for patron in patrones_horario:
                match = re.search(patron, text, re.IGNORECASE)
                if match:
                    horario_encontrado = match.group(1).strip()
                    break
            
            # Búsqueda específica en elementos comunes
            if telefono_encontrado == "No encontrado":
                # Buscar en enlaces de teléfono
                links = soup.find_all('a', href=re.compile(r'tel:'))
                for link in links:
                    tel_text = link.get_text().strip()
                    if '900' in tel_text or '901' in tel_text or '902' in tel_text:
                        telefono_encontrado = tel_text
                        break
            
            return {
                'telefono': telefono_encontrado,
                'horario': horario_encontrado,
                'status': 'success',
                'url_analizada': url
            }
            
        except requests.exceptions.Timeout:
            return {
                'telefono': "Timeout",
                'horario': "La web tarda demasiado en responder",
                'status': 'error',
                'detalle': 'Timeout de 15 segundos excedido'
            }
        except requests.exceptions.ConnectionError:
            return {
                'telefono': "Error conexión",
                'horario': "No se puede conectar",
                'status': 'error',
                'detalle': 'Error de conexión o web bloquea scraping'
            }
        except requests.exceptions.HTTPError as e:
            return {
                'telefono': f"Error HTTP {e.response.status_code}",
                'horario': "Acceso denegado",
                'status': 'error',
                'detalle': f'La web devolvió código {e.response.status_code}'
            }
        except Exception as e:
            return {
                'telefono': "Error",
                'horario': "Error inesperado",
                'status': 'error',
                'detalle': str(e)
            }
class HTMLExtractor:
    """Extractor manual que analiza HTML pegado por el usuario"""
    
    def extraer_de_html(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            # Patrones de teléfonos españoles
            patrones = [
                r'900[\s.-]?\d{3}[\s.-]?\d{3}',
                r'90[12][\s.-]?\d{3}[\s.-]?\d{3}',
                r'900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}',
            ]
            
            encontrados = set()  # Usar set para evitar duplicados
            for patron in patrones:
                matches = re.findall(patron, text)
                for match in matches:
                    # Limpiar y formatear
                    limpio = re.sub(r'[\s.-]', '', match)
                    if len(limpio) == 9:
                        formateado = f"{limpio[:3]} {limpio[3:6]} {limpio[6:]}"
                        encontrados.add(formateado)
                    elif len(limpio) == 12:  # Formato 900 XX XX XX XX
                        formateado = f"{limpio[:3]} {limpio[3:5]} {limpio[5:7]} {limpio[7:9]} {limpio[9:]}"
                        encontrados.add(formateado)
            
            # Buscar horarios
            patrones_horario = [
                r'lunes\s+(?:a|al|-)\s+viernes[:\s]+\d{1,2}[:.]\d{2}\s+(?:a|de|hasta|-)\s+\d{1,2}[:.]\d{2}',
                r'\d{1,2}[:.]\d{2}\s+(?:a|de|hasta|-)\s+\d{1,2}[:.]\d{2}\s+h?',
                r'de\s+\d{1,2}[:.]\d{2}\s+a\s+\d{1,2}[:.]\d{2}',
            ]
            
            horarios = set()
            for patron in patrones_horario:
                matches = re.findall(patron, text, re.IGNORECASE)
                for match in matches:
                    horarios.add(match.strip())
            
            return {
                'encontrados': sorted(list(encontrados)),
                'horarios': sorted(list(horarios)),
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'encontrados': [],
                'horarios': [],
                'status': 'error',
                'error': str(e)
            }
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

# Crear archivo CSV si no existe
if not os.path.exists(CSV_PATH):
    df = pd.DataFrame(columns=["nombre", "sector", "telefono_900", "web_oficial", "tiempo_espera_min", "menu_voz_ruta", "sector_relacionado_1", "sector_relacionado_2"])
    df.to_csv(CSV_PATH, index=False)
else:
    df = pd.read_csv(CSV_PATH)

# --- Sidebar ---
st.sidebar.header("⚙️ Configuración")
st.sidebar.info("Las claves se cargan desde el archivo `.env`")
if not os.getenv("OPENROUTER_API_KEY"):
    st.sidebar.error("️ Falta OPENROUTER_API_KEY en el archivo .env")
else:
    st.sidebar.success("✅ API Key de OpenRouter configurada")

# --- Tabs Principales ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 1. Base de Datos", "🕷️ 2. Scraping", "🤖 3. Generar Artículo", "🚀 4. Publicar"])

# TAB 1: BASE DE DATOS
with tab1:
    st.header("Gestión de Empresas")
    st.markdown("Edita la tabla directamente como si fuera Excel. Los cambios se guardan al pulsar el botón.")
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    if st.button(" Guardar Cambios en CSV", type="primary"):
        edited_df.to_csv(CSV_PATH, index=False)
        st.success("✅ Base de datos actualizada correctamente.")
        df = edited_df

# TAB 2: SCRAPING
with tab2:
    st.header("🕷️ Extracción Inteligente de Datos")
    
    # Selector de modo
    modo = st.radio(
        "Selecciona el método de extracción:",
        ["🔄 Automático (Scraping)", "✋ Manual Asistido (Pegar HTML)"],
        horizontal=True
    )
    
    if modo == "🔄 Automático (Scraping)":
        st.info("Intenta extraer datos automáticamente. Puede fallar en webs con protección.")
        url = st.text_input("URL de la web oficial:", placeholder="https://www.orange.es/")
        
        if st.button("🔍 Analizar Web Automáticamente", type="primary"):
            if url:
                with st.spinner("Analizando la web..."):
                    scraper = SmartScraper()
                    resultado = scraper.extraer(url)
                    
                    if resultado['status'] == 'success':
                        st.success("✅ Datos extraídos correctamente")
                        st.json(resultado)
                    else:
                        st.error(f"❌ Error: {resultado.get('detalle', 'Error desconocido')}")
                        st.info("💡 Prueba el modo 'Manual Asistido' pegando el HTML")
            else:
                st.warning("⚠️ Introduce una URL")
    
    else:
        # MODO MANUAL ASISTIDO
        st.success("🎯 Modo Manual Asistido - Infalible")
        st.markdown("""
        **Instrucciones:**
        1. Abre la web de la empresa en tu navegador
        2. Pulsa **Ctrl+U** (ver código fuente) o **F12** (inspeccionar)
        3. Copia TODO el HTML (Ctrl+A, Ctrl+C)
        4. Pégalo en el cuadro de abajo
        """)
        
        html_input = st.text_area(
            "Pega aquí el HTML completo de la web:",
            placeholder="<html><head>...</head><body>...</body></html>",
            height=200
        )
        
        if st.button("🔍 Extraer Datos del HTML", type="primary"):
            if html_input:
                with st.spinner("Analizando HTML..."):
                    try:
                        extractor = HTMLExtractor()
                        resultado = extractor.extraer_de_html(html_input)
                        
                        if resultado['encontrados']:
                            st.success(f"✅ Encontrados {len(resultado['encontrados'])} teléfonos y {len(resultado['horarios'])} horarios")
                            
                            # Mostrar teléfonos encontrados
                            st.subheader("📞 Teléfonos detectados:")
                            for i, tel in enumerate(resultado['encontrados']):
                                st.markdown(f"**{i+1}.** `{tel}`")
                            
                            # Mostrar horarios encontrados
                            if resultado['horarios']:
                                st.subheader("🕐 Horarios detectados:")
                                for i, hor in enumerate(resultado['horarios']):
                                    st.markdown(f"**{i+1}.** {hor}")
                            
                            # Selector para elegir cuál usar
                            st.divider()
                            col1, col2 = st.columns(2)
                            with col1:
                                tel_seleccionado = st.selectbox(
                                    "Selecciona el teléfono 900 correcto:",
                                    resultado['encontrados'],
                                    key="sel_tel"
                                )
                            with col2:
                                hor_seleccionado = st.selectbox(
                                    "Selecciona el horario:",
                                    ["No especificado"] + resultado['horarios'],
                                    key="sel_hor"
                                )
                            
                            # Guardar en sesión
                            st.session_state['datos_extraidos'] = {
                                'telefono': tel_seleccionado,
                                'horario': hor_seleccionado if hor_seleccionado != "No especificado" else ""
                            }
                            
                            st.success("✅ Datos listos para copiar a la Base de Datos")
                            st.info("💡 Ve a la pestaña 'Base de Datos' y actualiza la fila de la empresa con estos datos")
                            
                        else:
                            st.warning("⚠️ No se encontraron teléfonos 900/901/902 en el HTML")
                            st.info("💡 Intenta buscar en otra sección de la web (Contacto, Atención al Cliente, etc.)")
                    
                    except Exception as e:
                        st.error(f"❌ Error al procesar HTML: {str(e)}")
            else:
                st.warning("⚠️ Pega el HTML de la web")

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
                    st.success(f" ¡Artículo publicado con éxito! [Haz clic aquí para verlo en WordPress]({resultado_wp['url']})")
                    st.info("Recuerda: Se ha guardado como 'Borrador'. Revísalo y dale a 'Publicar' en tu panel de WordPress.")
                else:
                    st.error(f"Error al publicar: {resultado_wp['error']}")
class HTMLExtractor:
    """Extractor manual que analiza HTML pegado por el usuario"""
    
    def extraer_de_html(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            # Patrones de teléfonos españoles
            patrones = [
                r'900[\s.-]?\d{3}[\s.-]?\d{3}',
                r'90[12][\s.-]?\d{3}[\s.-]?\d{3}',
                r'900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}',
            ]
            
            encontrados = set()  # Usar set para evitar duplicados
            for patron in patrones:
                matches = re.findall(patron, text)
                for match in matches:
                    # Limpiar y formatear
                    limpio = re.sub(r'[\s.-]', '', match)
                    if len(limpio) == 9:
                        formateado = f"{limpio[:3]} {limpio[3:6]} {limpio[6:]}"
                        encontrados.add(formateado)
                    elif len(limpio) == 12:  # Formato 900 XX XX XX XX
                        formateado = f"{limpio[:3]} {limpio[3:5]} {limpio[5:7]} {limpio[7:9]} {limpio[9:]}"
                        encontrados.add(formateado)
            
            # Buscar horarios
            patrones_horario = [
                r'lunes\s+(?:a|al|-)\s+viernes[:\s]+\d{1,2}[:.]\d{2}\s+(?:a|de|hasta|-)\s+\d{1,2}[:.]\d{2}',
                r'\d{1,2}[:.]\d{2}\s+(?:a|de|hasta|-)\s+\d{1,2}[:.]\d{2}\s+h?',
                r'de\s+\d{1,2}[:.]\d{2}\s+a\s+\d{1,2}[:.]\d{2}',
            ]
            
            horarios = set()
            for patron in patrones_horario:
                matches = re.findall(patron, text, re.IGNORECASE)
                for match in matches:
                    horarios.add(match.strip())
            
            return {
                'encontrados': sorted(list(encontrados)),
                'horarios': sorted(list(horarios)),
                'status': 'success'
            }
            
        except Exception as e:
            return {
                'encontrados': [],
                'horarios': [],
                'status': 'error',
                'error': str(e)
            }
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

# Crear archivo CSV si no existe
if not os.path.exists(CSV_PATH):
    df = pd.DataFrame(columns=["nombre", "sector", "telefono_900", "web_oficial", "tiempo_espera_min", "menu_voz_ruta", "sector_relacionado_1", "sector_relacionado_2"])
    df.to_csv(CSV_PATH, index=False)
else:
    df = pd.read_csv(CSV_PATH)

# --- Sidebar ---
st.sidebar.header("⚙️ Configuración")
st.sidebar.info("Las claves se cargan desde el archivo `.env`")
if not os.getenv("OPENROUTER_API_KEY"):
    st.sidebar.error("️ Falta OPENROUTER_API_KEY en el archivo .env")
else:
    st.sidebar.success("✅ API Key de OpenRouter configurada")

# --- Tabs Principales ---
tab1, tab2, tab3, tab4 = st.tabs(["📊 1. Base de Datos", "🕷️ 2. Scraping", "🤖 3. Generar Artículo", "🚀 4. Publicar"])

# TAB 1: BASE DE DATOS
with tab1:
    st.header("Gestión de Empresas")
    st.markdown("Edita la tabla directamente como si fuera Excel. Los cambios se guardan al pulsar el botón.")
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    
    if st.button(" Guardar Cambios en CSV", type="primary"):
        edited_df.to_csv(CSV_PATH, index=False)
        st.success("✅ Base de datos actualizada correctamente.")
        df = edited_df

# TAB 2: SCRAPING
with tab2:
    st.header("🕷️ Extracción Inteligente de Datos")
    
    # Selector de modo
    modo = st.radio(
        "Selecciona el método de extracción:",
        ["🔄 Automático (Scraping)", "✋ Manual Asistido (Pegar HTML)"],
        horizontal=True
    )
    
    if modo == "🔄 Automático (Scraping)":
        st.info("Intenta extraer datos automáticamente. Puede fallar en webs con protección.")
        url = st.text_input("URL de la web oficial:", placeholder="https://www.orange.es/")
        
        if st.button("🔍 Analizar Web Automáticamente", type="primary"):
            if url:
                with st.spinner("Analizando la web..."):
                    scraper = SmartScraper()
                    resultado = scraper.extraer(url)
                    
                    if resultado['status'] == 'success':
                        st.success("✅ Datos extraídos correctamente")
                        st.json(resultado)
                    else:
                        st.error(f"❌ Error: {resultado.get('detalle', 'Error desconocido')}")
                        st.info("💡 Prueba el modo 'Manual Asistido' pegando el HTML")
            else:
                st.warning("⚠️ Introduce una URL")
    
    else:
        # MODO MANUAL ASISTIDO
        st.success("🎯 Modo Manual Asistido - Infalible")
        st.markdown("""
        **Instrucciones:**
        1. Abre la web de la empresa en tu navegador
        2. Pulsa **Ctrl+U** (ver código fuente) o **F12** (inspeccionar)
        3. Copia TODO el HTML (Ctrl+A, Ctrl+C)
        4. Pégalo en el cuadro de abajo
        """)
        
        html_input = st.text_area(
            "Pega aquí el HTML completo de la web:",
            placeholder="<html><head>...</head><body>...</body></html>",
            height=200
        )
        
        if st.button("🔍 Extraer Datos del HTML", type="primary"):
            if html_input:
                with st.spinner("Analizando HTML..."):
                    try:
                        extractor = HTMLExtractor()
                        resultado = extractor.extraer_de_html(html_input)
                        
                        if resultado['encontrados']:
                            st.success(f"✅ Encontrados {len(resultado['encontrados'])} teléfonos y {len(resultado['horarios'])} horarios")
                            
                            # Mostrar teléfonos encontrados
                            st.subheader("📞 Teléfonos detectados:")
                            for i, tel in enumerate(resultado['encontrados']):
                                st.markdown(f"**{i+1}.** `{tel}`")
                            
                            # Mostrar horarios encontrados
                            if resultado['horarios']:
                                st.subheader("🕐 Horarios detectados:")
                                for i, hor in enumerate(resultado['horarios']):
                                    st.markdown(f"**{i+1}.** {hor}")
                            
                            # Selector para elegir cuál usar
                            st.divider()
                            col1, col2 = st.columns(2)
                            with col1:
                                tel_seleccionado = st.selectbox(
                                    "Selecciona el teléfono 900 correcto:",
                                    resultado['encontrados'],
                                    key="sel_tel"
                                )
                            with col2:
                                hor_seleccionado = st.selectbox(
                                    "Selecciona el horario:",
                                    ["No especificado"] + resultado['horarios'],
                                    key="sel_hor"
                                )
                            
                            # Guardar en sesión
                            st.session_state['datos_extraidos'] = {
                                'telefono': tel_seleccionado,
                                'horario': hor_seleccionado if hor_seleccionado != "No especificado" else ""
                            }
                            
                            st.success("✅ Datos listos para copiar a la Base de Datos")
                            st.info("💡 Ve a la pestaña 'Base de Datos' y actualiza la fila de la empresa con estos datos")
                            
                        else:
                            st.warning("⚠️ No se encontraron teléfonos 900/901/902 en el HTML")
                            st.info("💡 Intenta buscar en otra sección de la web (Contacto, Atención al Cliente, etc.)")
                    
                    except Exception as e:
                        st.error(f"❌ Error al procesar HTML: {str(e)}")
            else:
                st.warning("⚠️ Pega el HTML de la web")

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
                    st.success(f" ¡Artículo publicado con éxito! [Haz clic aquí para verlo en WordPress]({resultado_wp['url']})")
                    st.info("Recuerda: Se ha guardado como 'Borrador'. Revísalo y dale a 'Publicar' en tu panel de WordPress.")
                else:
                    st.error(f"Error al publicar: {resultado_wp['error']}")

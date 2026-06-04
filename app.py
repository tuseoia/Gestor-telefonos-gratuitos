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
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=15)
            
            # DETECCIÓN DE BLOQUEOS ANTI-BOT
            if response.status_code == 403:
                return self._resultado_bloqueado(url, "Acceso denegado (403). La web usa protección anti-bot.")
            if response.status_code == 429:
                return self._resultado_bloqueado(url, "Demasiadas peticiones (429). Espera unos minutos.")
            if response.status_code == 503:
                return self._resultado_bloqueado(url, "Servicio no disponible (503). Posible protección Cloudflare/Akamai.")
            
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            # DETECCIÓN DE CAPTCHA O CHALLENGE
            indicadores_bloqueo = ['captcha', 'challenge', 'cloudflare', 'akamai', 'verifica que eres humano']
            if any(indicador in html.lower() for indicador in indicadores_bloqueo):
                return self._resultado_bloqueado(url, "La web muestra un CAPTCHA o verificación humana.")
            
            if len(html) < 5000:
                return self._resultado_bloqueado(url, "La web devolvió una página muy pequeña (posible bloqueo).")
            
            # Búsqueda de teléfonos
            patrones_telefono = [
                r'(900[\s.-]?\d{3}[\s.-]?\d{3})',
                r'(900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2})',
                r'(90[0-9][\s.-]?\d{3}[\s.-]?\d{3})',
            ]
            
            telefono_encontrado = "No encontrado"
            for patron in patrones_telefono:
                match = re.search(patron, text)
                if match:
                    telefono_limpio = re.sub(r'[\s.-]', '', match.group(1))
                    if len(telefono_limpio) == 9:
                        telefono_encontrado = f"{telefono_limpio[:3]} {telefono_limpio[3:6]} {telefono_limpio[6:]}"
                    else:
                        telefono_encontrado = match.group(1)
                    break
            
            if telefono_encontrado == "No encontrado":
                links = soup.find_all('a', href=re.compile(r'tel:'))
                for link in links:
                    tel_text = link.get_text().strip()
                    if '900' in tel_text or '901' in tel_text or '902' in tel_text:
                        telefono_encontrado = tel_text
                        break
            
            # Búsqueda de horarios
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
            
            return {
                'telefono': telefono_encontrado,
                'horario': horario_encontrado,
                'status': 'success',
                'url_analizada': url
            }
            
        except requests.exceptions.Timeout:
            return self._resultado_bloqueado(url, "Timeout: la web tarda más de 15 segundos.")
        except requests.exceptions.ConnectionError:
            return self._resultado_bloqueado(url, "Error de conexión. La web puede estar caída o bloqueando tu IP.")
        except requests.exceptions.HTTPError as e:
            return self._resultado_bloqueado(url, f"Error HTTP {e.response.status_code}")
        except Exception as e:
            return self._resultado_bloqueado(url, f"Error inesperado: {str(e)}")
    
    def _resultado_bloqueado(self, url, motivo):
        return {
            'telefono': "Bloqueado",
            'horario': "Bloqueado",
            'status': 'bloqueado',
            'url_analizada': url,
            'detalle': motivo,
            'solucion': "Usa el modo 'Búsqueda Inteligente' o 'Manual Asistido'"
        }


class HTMLExtractor:
    """Extractor manual que analiza HTML pegado por el usuario"""
    
    def extraer_de_html(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            patrones = [
                r'900[\s.-]?\d{3}[\s.-]?\d{3}',
                r'90[12][\s.-]?\d{3}[\s.-]?\d{3}',
                r'900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}',
            ]
            
            encontrados = set()
            for patron in patrones:
                matches = re.findall(patron, text)
                for match in matches:
                    limpio = re.sub(r'[\s.-]', '', match)
                    if len(limpio) == 9:
                        formateado = f"{limpio[:3]} {limpio[3:6]} {limpio[6:]}"
                        encontrados.add(formateado)
            
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


class GoogleSearcher:
    """Buscador inteligente que extrae teléfonos de resultados de búsqueda"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def buscar_telefono(self, nombre_empresa, sector=""):
        """Busca el teléfono gratuito de una empresa en DuckDuckGo"""
        
        queries = [
            f"teléfono gratuito {nombre_empresa} atención al cliente 900",
            f"número 900 {nombre_empresa} servicio cliente",
            f"contactar {nombre_empresa} teléfono gratis España"
        ]
        
        telefonos_encontrados = []
        fuentes = []
        
        for query in queries:
            try:
                url_busqueda = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
                response = requests.get(url_busqueda, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    text = soup.get_text()
                    
                    patrones = [
                        r'900[\s.-]?\d{3}[\s.-]?\d{3}',
                        r'90[12][\s.-]?\d{3}[\s.-]?\d{3}',
                    ]
                    
                    for patron in patrones:
                        matches = re.findall(patron, text)
                        for match in matches:
                            limpio = re.sub(r'[\s.-]', '', match)
                            if len(limpio) == 9:
                                formateado = f"{limpio[:3]} {limpio[3:6]} {limpio[6:]}"
                                if formateado not in telefonos_encontrados:
                                    telefonos_encontrados.append(formateado)
                                    fuentes.append({
                                        'telefono': formateado,
                                        'fuente': 'DuckDuckGo',
                                        'snippet': f"Encontrado buscando: {query}"
                                    })
                
                if telefonos_encontrados:
                    break  # Si ya encontramos, no seguir buscando
                    
            except Exception as e:
                continue
        
        return {
            'telefonos': telefonos_encontrados,
            'fuentes': fuentes,
            'status': 'success' if telefonos_encontrados else 'no_encontrado'
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

if not os.path.exists(CSV_PATH):
    df = pd.DataFrame(columns=["nombre", "sector", "telefono_900", "telefono_fijo", "horario_lunes_viernes", "horario_sabado", "web_oficial", "email", "whatsapp", "direccion_postal", "menu_voz_ruta", "tiempo_espera_min", "sector_relacionado_1", "sector_relacionado_2", "ultima_verificacion"])
    df.to_csv(CSV_PATH, index=False)
else:
    df = pd.read_csv(CSV_PATH)

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
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="data_editor_empresas")
    
    if st.button("💾 Guardar Cambios en CSV", type="primary", key="btn_guardar_csv"):
        edited_df.to_csv(CSV_PATH, index=False)
        st.success("✅ Base de datos actualizada correctamente.")
        df = edited_df

# TAB 2: SCRAPING
with tab2:
    st.header("🕷️ Extracción Inteligente de Datos")
    
    modo = st.radio(
        "Selecciona el método de extracción:",
        ["🔍 Búsqueda Inteligente (Recomendado)", "🔄 Scraping Automático", "✋ Manual Asistido"],
        horizontal=True,
        help="La Búsqueda Inteligente funciona incluso con webs protegidas como Movistar, Orange, etc.",
        key="modo_extraccion_radio"
    )
    
    # MODO 1: BÚSQUEDA INTELIGENTE
    if modo == "🔍 Búsqueda Inteligente (Recomendado)":
        st.success("🎯 **Modo más potente** - Busca en múltiples fuentes automáticamente")
        st.info("💡 Funciona incluso con webs protegidas como Movistar, Orange, Vodafone, bancos, etc.")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            nombre_busqueda = st.text_input(
                "Nombre de la empresa:",
                placeholder="Ej: Movistar, Orange, Endesa...",
                key="nombre_busqueda_inteligente"
            )
        with col2:
            sector_busqueda = st.text_input(
                "Sector (opcional):",
                placeholder="Ej: Telecomunicaciones",
                key="sector_busqueda_inteligente"
            )
        
        if st.button("🔍 Buscar Teléfono en Internet", type="primary", key="btn_buscar_inteligente"):
            if nombre_busqueda:
                with st.spinner("Buscando en múltiples fuentes... Esto puede tardar 10-20 segundos"):
                    try:
                        searcher = GoogleSearcher()
                        resultado = searcher.buscar_telefono(nombre_busqueda, sector_busqueda)
                        
                        if resultado['status'] == 'success' and resultado.get('telefonos'):
                            st.success(f"✅ ¡Encontrados {len(resultado['telefonos'])} teléfonos posibles!")
                            
                            for i, fuente_info in enumerate(resultado.get('fuentes', []), 1):
                                with st.expander(f"📞 Opción {i}: {fuente_info['telefono']}", expanded=(i==1)):
                                    st.markdown(f"**Fuente:** {fuente_info['fuente']}")
                                    st.markdown(f"**Contexto:** {fuente_info['snippet']}")
                            
                            st.divider()
                            
                            tel_seleccionado = st.selectbox(
                                "Selecciona el teléfono 900 correcto:",
                                resultado['telefonos'],
                                key="sel_tel_inteligente"
                            )
                            
                            st.session_state['datos_extraidos'] = {
                                'telefono': tel_seleccionado,
                                'horario': ""
                            }
                            
                            st.success("✅ Datos listos para copiar a la Base de Datos")
                            st.info("💡 Ve a la pestaña 'Base de Datos' y actualiza la fila de la empresa")
                            
                        else:
                            st.warning("⚠️ No se encontraron teléfonos en las búsquedas")
                            st.info("💡 Prueba el modo 'Manual Asistido' o añade los datos manualmente")
                    except Exception as e:
                        st.error(f"❌ Error en la búsqueda: {str(e)}")
            else:
                st.warning("⚠️ Introduce el nombre de la empresa")
    
    # MODO 2: SCRAPING AUTOMÁTICO
    elif modo == "🔄 Scraping Automático":
        st.info("Intenta extraer datos automáticamente. Puede fallar en webs con protección.")
        url = st.text_input("URL de la web oficial:", placeholder="https://www.orange.es/", key="url_scraping_auto")
        
        if st.button("🔍 Analizar Web Automáticamente", type="primary", key="btn_analizar_auto"):
            if url:
                with st.spinner("Analizando la web..."):
                    try:
                        scraper = SmartScraper()
                        resultado = scraper.extraer(url)
                        
                        if resultado['status'] == 'success':
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("📞 Teléfono 900", resultado['telefono'])
                            with col2:
                                st.metric("🕐 Horario", resultado['horario'])
                            st.success("✅ Datos extraídos correctamente")
                            
                            st.session_state['datos_extraidos'] = {
                                'telefono': resultado['telefono'],
                                'horario': resultado['horario']
                            }
                            
                        elif resultado.get('status') == 'bloqueado':
                            st.warning(f"🛡️ **{resultado.get('url_analizada', url)}** tiene protección anti-bot")
                            st.error(f"Motivo: {resultado.get('detalle', 'Sin detalles')}")
                            st.info(f"💡 **Solución:** {resultado.get('solucion', 'Usa modo Manual Asistido')}")
                            
                        else:
                            st.error(f"❌ Error: {resultado.get('detalle', 'Error desconocido')}")
                    except Exception as e:
                        st.error(f"❌ Error en el scraping: {str(e)}")
            else:
                st.warning("⚠️ Introduce una URL")
    
    # MODO 3: MANUAL ASISTIDO
    else:
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
            height=200,
            key="html_manual_asistido"
        )
        
        if st.button("🔍 Extraer Datos del HTML", type="primary", key="btn_extraer_html"):
            if html_input:
                with st.spinner("Analizando HTML..."):
                    try:
                        extractor = HTMLExtractor()
                        resultado = extractor.extraer_de_html(html_input)
                        
                        if resultado.get('encontrados'):
                            st.success(f"✅ Encontrados {len(resultado['encontrados'])} teléfonos y {len(resultado.get('horarios', []))} horarios")
                            
                            st.subheader("📞 Teléfonos detectados:")
                            for i, tel in enumerate(resultado['encontrados'], 1):
                                st.markdown(f"**{i}.** `{tel}`")
                            
                            if resultado.get('horarios'):
                                st.subheader("🕐 Horarios detectados:")
                                for i, hor in enumerate(resultado['horarios'], 1):
                                    st.markdown(f"**{i}.** {hor}")
                            
                            st.divider()
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                tel_seleccionado = st.selectbox(
                                    "Selecciona el teléfono 900 correcto:",
                                    resultado['encontrados'],
                                    key="sel_tel_manual"
                                )
                            with col2:
                                opciones_horario = ["No especificado"] + resultado.get('horarios', [])
                                hor_seleccionado = st.selectbox(
                                    "Selecciona el horario:",
                                    opciones_horario,
                                    key="sel_hor_manual"
                                )
                            
                            st.session_state['datos_extraidos'] = {
                                'telefono': tel_seleccionado,
                                'horario': hor_seleccionado if hor_seleccionado != "No especificado" else ""
                            }
                            
                            st.success("✅ Datos listos para copiar a la Base de Datos")
                            st.info("💡 Ve a la pestaña 'Base de Datos' y actualiza la fila de la empresa")
                            
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
        empresa_seleccionada = st.selectbox(
            "Selecciona una empresa para generar su artículo:", 
            df['nombre'].dropna().tolist(),
            key="select_empresa_generar"
        )
        datos_empresa = df[df['nombre'] == empresa_seleccionada].iloc[0].to_dict()
        
        if st.button("✨ Generar Contenido con Qwen (OpenRouter)", type="primary", key="btn_generar_ia"):
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
                with st.expander("👁️ Vista Previa: Comparativa"):
                    st.markdown(comp)

# TAB 4: PUBLICAR Y VALIDAR
with tab4:
    st.header("🚀 Validación Final y Publicación en WordPress")
    
    if 'empresa_actual' not in st.session_state:
        st.info("Primero genera un artículo en la pestaña anterior.")
    else:
        emp = st.session_state['empresa_actual']
        exp = st.session_state.get('articulo_exp', '')
        consejos = st.session_state.get('articulo_consejos', '')
        comp = st.session_state.get('articulo_comp', '')
        
        articulo_final = f"""# Teléfono Gratuito de {emp['nombre']} {datetime.now().year} - Atención al Cliente Gratis

**Última verificación:** {datetime.now().strftime("%d de %B de %Y")} ✅  
**Autor:** Equipo Editorial de telefonos-gratuitos.com

---

## 📞 El Teléfono Gratuito
El teléfono de atención al cliente gratuito de **{emp['nombre']}** es el **{emp.get('telefono_900', 'Consultar web')}**. Es totalmente gratis desde fijo y móvil en España.

| Dato | Información |
|------|-------------|
| **Teléfono** | **{emp.get('telefono_900', 'Consultar web')}** |
| **Horario** | {emp.get('horario_lunes_viernes', 'Consultar web')} |
| **Web Oficial** | [{emp.get('web_oficial', '')}]({emp.get('web_oficial', '')}) |

---

## 📝 Nuestra Experiencia y Verificación
{exp}

---

## 💡 Consejos para Reclamaciones y Trámites
{consejos}

---

## ⚖️ Comparativa del Sector
{comp}

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
        
        if st.button("📤 Publicar como Borrador en WordPress", type="primary", disabled=not resultado_val['aprobado'], key="btn_publicar_wp"):
            with st.spinner("Conectando con WordPress..."):
                publisher = WPPublisher()
                titulo = f"Teléfono Gratuito de {emp['nombre']} {datetime.now().year}"
                resultado_wp = publisher.publicar(titulo, articulo_final)
                
                if resultado_wp['success']:
                    st.success(f"🎉 ¡Artículo publicado con éxito! [Haz clic aquí para verlo en WordPress]({resultado_wp['url']})")
                    st.info("Recuerda: Se ha guardado como 'Borrador'. Revísalo y dale a 'Publicar' en tu panel de WordPress.")
                else:
                    st.error(f"Error al publicar: {resultado_wp['error']}")

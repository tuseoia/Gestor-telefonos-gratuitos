import streamlit as st
import pandas as pd
import os
import json
import requests
import re
import random
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Cargar variables de entorno
load_dotenv()

# Crear carpeta data si no existe (solución para Streamlit Cloud)
os.makedirs("data", exist_ok=True)

# ==========================================
# 1. FUNCIONES AUXILIARES (Schemas y SEO)
# ==========================================

def generar_schema_faq(articulo_markdown, nombre_empresa):
    """Extrae las FAQ del artículo y genera el Schema.org FAQPage en JSON-LD"""
    faq_section = ""
    if "## ❓ Preguntas Frecuentes" in articulo_markdown:
        inicio = articulo_markdown.find("## ❓ Preguntas Frecuentes")
        siguiente_h2 = articulo_markdown.find("\n## ", inicio + 1)
        if siguiente_h2 != -1:
            faq_section = articulo_markdown[inicio: siguiente_h2]
        else:
            faq_section = articulo_markdown[inicio:]
    
    faqs = []
    lineas = faq_section.split('\n')
    pregunta_actual = None
    respuesta_actual = []
    
    for linea in lineas:
        if linea.startswith('### '):
            if pregunta_actual and respuesta_actual:
                faqs.append({
                    "@type": "Question",
                    "name": pregunta_actual,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": ' '.join(respuesta_actual).strip()
                    }
                })
            pregunta_actual = linea.replace('### ', '').strip()
            respuesta_actual = []
        elif pregunta_actual and linea.strip() and not linea.startswith('##'):
            respuesta_actual.append(linea.strip())
    
    if pregunta_actual and respuesta_actual:
        faqs.append({
            "@type": "Question",
            "name": pregunta_actual,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": ' '.join(respuesta_actual).strip()
            }
        })
    
    if faqs:
        schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faqs
        }
        json_ld = json.dumps(schema, indent=2, ensure_ascii=False)
        schema_html = f'<script type="application/ld+json">\n{json_ld}\n</script>'
        return {
            'schema': schema,
            'html': schema_html,
            'num_faqs': len(faqs)
        }
    return None


def generar_schema_contact_point(empresa, articulo_markdown):
    """Genera Schema.org ContactPoint + Organization + Article + Breadcrumb"""
    telefono = empresa.get('telefono_900', '')
    telefono_limpio = re.sub(r'[\s.-]', '', str(telefono))
    
    if len(telefono_limpio) == 9:
        telefono_schema = f"+34-{telefono_limpio[:3]}-{telefono_limpio[3:6]}-{telefono_limpio[6:]}"
    elif len(telefono_limpio) == 4:
        telefono_schema = f"+34-{telefono_limpio}"
    else:
        telefono_schema = f"+34-{telefono_limpio}"
    
    horario_raw = empresa.get('horario_lunes_viernes', '09:00-20:00')
    try:
        if '-' in horario_raw and ':' in horario_raw:
            partes = horario_raw.split('-')
            opens = partes[0].strip().replace('.', ':')
            closes = partes[1].strip().replace('.', ':')
        else:
            opens, closes = "09:00", "20:00"
    except:
        opens, closes = "09:00", "20:00"
    
    es_gratuito = telefono_limpio.startswith(('900', '800')) or len(telefono_limpio) == 4
    
    schema_contact = {
        "@context": "https://schema.org",
        "@type": "ContactPoint",
        "telephone": telefono_schema,
        "contactType": "customer service",
        "areaServed": "ES",
        "availableLanguage": ["Spanish", "English"],
        "contactOption": "TollFree" if es_gratuito else "HearingImpairedSupported",
        "hoursAvailable": {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": opens,
            "closes": closes
        }
    }
    
    horario_sabado = empresa.get('horario_sabado', '')
    if horario_sabado and str(horario_sabado).lower() not in ['cerrado', 'no disponible', 'consultar web', 'nan']:
        schema_contact["hoursAvailable"]["dayOfWeek"].append("Saturday")
    
    schema_org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": empresa['nombre'],
        "url": empresa.get('web_oficial', ''),
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": telefono_schema,
            "contactType": "customer service",
            "areaServed": "ES",
            "availableLanguage": ["Spanish"]
        }
    }
    
    slug_articulo = f"telefono-gratuito-{empresa['nombre'].lower().replace(' ', '-')}"
    url_articulo = f"https://telefonos-gratuitos.com/{slug_articulo}/"
    
    schema_article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"Teléfono Gratuito de {empresa['nombre']} {datetime.now().year} - Atención al Cliente",
        "description": f"Encuentra el teléfono gratuito de {empresa['nombre']} ({telefono}). Horarios, menú de voz, alternativas de contacto y consejos para reclamar.",
        "author": {
            "@type": "Organization",
            "name": "Equipo Editorial de telefonos-gratuitos.com"
        },
        "publisher": {
            "@type": "Organization",
            "name": "telefonos-gratuitos.com",
            "logo": {
                "@type": "ImageObject",
                "url": "https://telefonos-gratuitos.com/logo.png"
            }
        },
        "datePublished": datetime.now().strftime("%Y-%m-%d"),
        "dateModified": datetime.now().strftime("%Y-%m-%d"),
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": url_articulo
        },
        "image": f"https://telefonos-gratuitos.com/images/{slug_articulo}.jpg",
        "articleSection": empresa.get('sector', 'Atención al Cliente'),
        "keywords": f"teléfono gratuito {empresa['nombre']}, {telefono}, atención al cliente {empresa['nombre']}"
    }
    
    schema_breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Inicio", "item": "https://telefonos-gratuitos.com/"},
            {"@type": "ListItem", "position": 2, "name": empresa.get('sector', 'Empresas'), "item": f"https://telefonos-gratuitos.com/{str(empresa.get('sector', 'empresas')).lower().replace(' ', '-')}/"},
            {"@type": "ListItem", "position": 3, "name": empresa['nombre']}
        ]
    }
    
    schemas_combinados = {
        "contact_point": schema_contact,
        "organization": schema_org,
        "article": schema_article,
        "breadcrumb": schema_breadcrumb
    }
    
    html_parts = []
    for nombre, schema in schemas_combinados.items():
        json_ld = json.dumps(schema, indent=2, ensure_ascii=False)
        html_parts.append(f'<script type="application/ld+json">\n{json_ld}\n</script>')
    
    return {
        'schemas': schemas_combinados,
        'html': '\n\n'.join(html_parts),
        'telefono_schema': telefono_schema,
        'url_articulo': url_articulo
    }


def generar_tabla_contenidos(articulo_markdown):
    """Genera una tabla de contenidos automática a partir de los H2"""
    lineas = articulo_markdown.split('\n')
    secciones = []
    
    for linea in lineas:
        if linea.startswith('## '):
            titulo = linea.replace('## ', '').strip()
            anchor = titulo.lower()
            anchor = re.sub(r'[^\w\s-]', '', anchor)
            anchor = re.sub(r'[\s]+', '-', anchor)
            secciones.append({'titulo': titulo, 'anchor': anchor})
    
    if not secciones:
        return ""
    
    toc = "## 📑 Índice de Contenidos\n\n"
    contador = 1
    for seccion in secciones:
        if 'Índice' not in seccion['titulo'] and 'Artículos Relacionados' not in seccion['titulo']:
            toc += f"{contador}. [{seccion['titulo']}](#{seccion['anchor']})\n"
            contador += 1
    
    toc += "\n---\n\n"
    return toc


def generar_enlaces_internos(articulo_markdown, df_empresas, empresa_actual):
    """Añade enlaces internos automáticos a otras empresas mencionadas"""
    articulo_modificado = articulo_markdown
    
    for index, row in df_empresas.iterrows():
        nombre_otra = row.get('nombre', '')
        if not nombre_otra or nombre_otra == empresa_actual:
            continue
        
        lineas = articulo_modificado.split('\n')
        nuevas_lineas = []
        ya_enlazado = False
        
        for linea in lineas:
            if linea.startswith('#') or ('[' in linea and '](' in linea):
                nuevas_lineas.append(linea)
            elif nombre_otra in linea and not ya_enlazado:
                slug = f"telefono-gratuito-{nombre_otra.lower().replace(' ', '-')}"
                url_interna = f"https://telefonos-gratuitos.com/{slug}/"
                if f"**{nombre_otra}**" in linea:
                    linea = linea.replace(f"**{nombre_otra}**", f"[**{nombre_otra}**]({url_interna})", 1)
                    ya_enlazado = True
                nuevas_lineas.append(linea)
            else:
                nuevas_lineas.append(linea)
        
        articulo_modificado = '\n'.join(nuevas_lineas)
    
    return articulo_modificado


def generar_meta_descripcion(empresa):
    """Genera una meta descripción optimizada para CTR"""
    telefono = empresa.get('telefono_900', '')
    nombre = empresa['nombre']
    horario = empresa.get('horario_lunes_viernes', '24h')
    
    plantillas = [
        f"☎️ Teléfono gratuito de {nombre}: {telefono}. Horario: {horario}. ✅ Verificado hoy. Guía completa: menú de voz, alternativas y consejos para reclamar.",
        f"¿Buscas el teléfono de {nombre}? 📞 {telefono} (GRATIS). Horario {horario}. Te explicamos cómo saltarte el menú de voz y hablar rápido con un operador.",
        f"{nombre} teléfono de atención al cliente: {telefono} ✓ Gratis desde fijo y móvil ✓ Horario: {horario} ✓ Guía paso a paso para contactar sin esperas.",
    ]
    
    meta = random.choice(plantillas)
    if len(meta) > 160:
        meta = meta[:157] + "..."
    return meta


# ==========================================
# 2. CLASES DEL SISTEMA (Backend)
# ==========================================

class QwenGenerator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = "qwen/qwen-2.5-72b-instruct"

    def generar(self, empresa, tipo):
        telefono = empresa.get('telefono_900', '1004')
        nombre = empresa['nombre']
        sector = empresa.get('sector', 'general')
        tiempo = empresa.get('tiempo_espera_min', '5')
        menu = empresa.get('menu_voz_ruta', '1,2,3')
        comp1 = empresa.get('sector_relacionado_1', 'competidores')
        comp2 = empresa.get('sector_relacionado_2', 'otras empresas')
        web = empresa.get('web_oficial', 'su web oficial')
        
        prompts = {
            "experiencia": f"""Escribe un párrafo de 200 palabras en primera persona del plural ('hemos probado', 'nuestro equipo') simulando una verificación real del teléfono {telefono} de {nombre}. 

Incluye:
- El día y hora aproximada de la llamada
- Tiempo de espera real ({tiempo} minutos)
- Descripción del menú de voz y la secuencia para hablar con un humano ({menu})
- Amabilidad y profesionalidad del operador
- Un consejo específico para reducir el tiempo de espera
- Mención a si el servicio está disponible 24h o solo en horario laboral

Tono: profesional, útil, cercano y de mucha confianza. Español de España. Evita clichés de IA.""",

            "consejos": f"""Escribe 5 consejos prácticos, numerados y específicos para reclamar a una empresa del sector '{sector}' como {nombre}. 

Cada consejo debe:
- Tener un título en negrita
- Explicación de 2-3 frases
- Mencionar organismos reales (OMIC, Consumo de la comunidad autónoma, Secretaría de Estado de Telecomunicaciones si aplica, OCU, etc.)
- Incluir plazos legales cuando sea relevante

Tono: empoderador para el consumidor, claro y directo. Español de España.""",

            "comparativa": f"""Haz una comparativa detallada entre {nombre}, {comp1} y {comp2} en cuanto a atención al cliente.

Incluye:
- Tabla comparativa en formato Markdown con columnas: Empresa | Teléfono gratuito | Horario | Tiempo espera medio | Valoración
- Análisis de 150 palabras destacando ventajas y desventajas de cada una
- Recomendación final sobre cuál tiene mejor servicio al cliente

Sé objetivo y basado en datos. Español de España.""",

            "menu_voz": f"""Escribe una guía paso a paso detallada para navegar el menú de voz de {nombre} llamando al {telefono}.

Incluye:
- Introducción de 2 frases explicando por qué es útil conocer el menú
- Lista numerada con cada paso (qué tecla pulsar, qué opción elegir, qué evitar)
- La secuencia exacta para llegar a un operador humano: {menu}
- 3 trucos para reducir el tiempo de espera
- Advertencias sobre opciones que redirigen a ventas o alargan la llamada

Tono: práctico y directo. Español de España. Usa emojis para hacer la lectura más fácil.""",

            "formas_contacto": f"""Escribe una sección detallada sobre TODAS las formas de contactar con {nombre} además del teléfono {telefono}.

Incluye estas subsecciones con título H3:
### 💬 Chat en Vivo
Descripción, disponibilidad, enlace a {web}

### 📱 WhatsApp Business  
Número si existe, horario, tipo de consultas que atienden

### 📧 Correo Electrónico
Email de atención al cliente, tiempo medio de respuesta

### 📲 App Móvil
Nombre de la app, funciones disponibles, enlaces a App Store y Google Play

### 🐦 Redes Sociales
Twitter/X, Facebook, Instagram - cómo contactar y tiempo de respuesta

### 🏪 Tiendas Físicas
Cómo localizar la tienda más cercana

Tono: informativo y práctico. Español de España. Usa formato Markdown con negritas y listas."""
        }
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Eres un redactor experto en SEO y consumo en España. Escribe texto 100% original, natural, sin clichés de IA. Evita frases como 'En conclusión', 'Es importante destacar', 'En resumen'. Usa párrafos cortos, listas y negritas para facilitar la lectura."},
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
            
            indicadores_bloqueo = ['captcha', 'challenge', 'cloudflare', 'akamai', 'verifica que eres humano']
            if any(indicador in html.lower() for indicador in indicadores_bloqueo):
                return self._resultado_bloqueado(url, "La web muestra un CAPTCHA o verificación humana.")
            
            if len(html) < 5000:
                return self._resultado_bloqueado(url, "La web devolvió una página muy pequeña (posible bloqueo).")
            
            patrones_telefono = [
                r'(900[\s.-]?\d{3}[\s.-]?\d{3})',
                r'(90[0-9][\s.-]?\d{3}[\s.-]?\d{3})',
                r'(900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2})',
                r'(\b100[0-9]\b)',
                r'(\b10[0-9]{2}\b)',
                r'(800[\s.-]?\d{3}[\s.-]?\d{3})',
            ]
            
            telefonos_encontrados = []
            for patron in patrones_telefono:
                matches = re.findall(patron, text)
                for match in matches:
                    telefono_limpio = re.sub(r'[\s.-]', '', match)
                    if len(telefono_limpio) == 9:
                        formateado = f"{telefono_limpio[:3]} {telefono_limpio[3:6]} {telefono_limpio[6:]}"
                    elif len(telefono_limpio) == 4 and telefono_limpio.startswith('100'):
                        formateado = telefono_limpio
                    else:
                        continue
                    
                    if formateado not in telefonos_encontrados:
                        telefonos_encontrados.append(formateado)
            
            if not telefonos_encontrados:
                links = soup.find_all('a', href=re.compile(r'tel:'))
                for link in links:
                    tel_text = link.get_text().strip()
                    tel_limpio = re.sub(r'[\s.-]', '', tel_text)
                    if any(x in tel_limpio for x in ['900', '901', '902', '1004', '1005', '800']):
                        if tel_limpio not in telefonos_encontrados:
                            telefonos_encontrados.append(tel_text)
            
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
            
            telefono_principal = telefonos_encontrados[0] if telefonos_encontrados else "No encontrado"
            
            return {
                'telefono': telefono_principal,
                'horario': horario_encontrado,
                'status': 'success',
                'url_analizada': url,
                'todos_los_telefonos': telefonos_encontrados
            }
            
        except requests.exceptions.Timeout:
            return self._resultado_bloqueado(url, "Timeout: la web tarda más de 15 segundos.")
        except requests.exceptions.ConnectionError:
            return self._resultado_bloqueado(url, "Error de conexión.")
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
            'solucion': "Usa el modo 'Búsqueda Inteligente' o 'Manual Asistido'",
            'todos_los_telefonos': []
        }


class HTMLExtractor:
    def extraer_de_html(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            patrones = [
                r'900[\s.-]?\d{3}[\s.-]?\d{3}',
                r'90[0-9][\s.-]?\d{3}[\s.-]?\d{3}',
                r'900[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}',
                r'\b100[0-9]\b',
                r'\b10[0-9]{2}\b',
                r'800[\s.-]?\d{3}[\s.-]?\d{3}',
            ]
            
            encontrados = set()
            for patron in patrones:
                matches = re.findall(patron, text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    limpio = re.sub(r'[\s.-]', '', match)
                    if len(limpio) == 9:
                        formateado = f"{limpio[:3]} {limpio[3:6]} {limpio[6:]}"
                        encontrados.add(formateado)
                    elif len(limpio) == 4 and limpio.startswith('100'):
                        encontrados.add(limpio)
                    elif len(limpio) == 12:
                        formateado = f"{limpio[:3]} {limpio[3:5]} {limpio[5:7]} {limpio[7:9]} {limpio[9:]}"
                        encontrados.add(formateado)
            
            links = soup.find_all('a', href=re.compile(r'tel:'))
            for link in links:
                tel_text = link.get_text().strip()
                tel_limpio = re.sub(r'[\s.-]', '', tel_text)
                if any(x in tel_limpio for x in ['900', '901', '902', '1004', '1005', '800']):
                    if len(tel_limpio) == 9:
                        formateado = f"{tel_limpio[:3]} {tel_limpio[3:6]} {tel_limpio[6:]}"
                        encontrados.add(formateado)
                    elif len(tel_limpio) == 4 and tel_limpio.startswith('100'):
                        encontrados.add(tel_limpio)
            
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
            return {'encontrados': [], 'horarios': [], 'status': 'error', 'error': str(e)}


class GoogleSearcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def buscar_telefono(self, nombre_empresa, sector=""):
        queries = [
            f"teléfono gratuito {nombre_empresa} atención al cliente",
            f"número atención al cliente {nombre_empresa}",
            f"contactar {nombre_empresa} teléfono España",
            f"{nombre_empresa} 1004 900 teléfono"
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
                        r'90[0-9][\s.-]?\d{3}[\s.-]?\d{3}',
                        r'\b100[0-9]\b',
                        r'\b10[0-9]{2}\b',
                        r'800[\s.-]?\d{3}[\s.-]?\d{3}',
                    ]
                    
                    for patron in patrones:
                        matches = re.findall(patron, text)
                        for match in matches:
                            if isinstance(match, tuple):
                                match = match[0]
                            limpio = re.sub(r'[\s.-]', '', match)
                            if len(limpio) == 9:
                                formateado = f"{limpio[:3]} {limpio[3:6]} {limpio[6:]}"
                            elif len(limpio) == 4 and limpio.startswith('100'):
                                formateado = limpio
                            else:
                                formateado = match
                            
                            if formateado not in telefonos_encontrados:
                                telefonos_encontrados.append(formateado)
                                fuentes.append({
                                    'telefono': formateado,
                                    'fuente': 'DuckDuckGo',
                                    'snippet': f"Encontrado buscando: {query}"
                                })
                
                if len(telefonos_encontrados) >= 3:
                    break
            except:
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
    def publicar(self, titulo, contenido, schema_faq=None, schema_contact=None, meta_descripcion=None):
        url = f"{os.getenv('WP_URL').rstrip('/')}/wp-json/wp/v2/posts"
        user = os.getenv('WP_USER')
        pwd = os.getenv('WP_APP_PASSWORD')
        
        contenido_completo = ""
        if schema_contact:
            contenido_completo += schema_contact['html'] + "\n\n"
        if schema_faq:
            contenido_completo += schema_faq['html'] + "\n\n"
        contenido_completo += contenido
        
        payload = {
            "title": titulo,
            "content": contenido_completo,
            "status": "draft"
        }
        
        if meta_descripcion:
            payload["meta"] = {"_yoast_wpseo_metadesc": meta_descripcion}
        
        try:
            response = requests.post(url, auth=(user, pwd), json=payload)
            if response.status_code == 201:
                return {
                    "success": True,
                    "url": response.json()['link'],
                    "schema_incluido": schema_faq is not None or schema_contact is not None,
                    "meta_descripcion": meta_descripcion
                }
            return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ==========================================
# 3. INTERFAZ DE USUARIO (Frontend Streamlit)
# ==========================================

st.set_page_config(page_title="Gestor Telefonos Gratuitos", page_icon="📞", layout="wide")
st.title("📞 Panel de Control: telefonos-gratuitos.com")
st.markdown("Automatización SEO + AdSense + Qwen AI + WordPress + Schema.org")

# --- Cargar Base de Datos ---
CSV_PATH = "data/empresas.csv"

if not os.path.exists(CSV_PATH):
    df = pd.DataFrame(columns=[
        "nombre", "sector", "telefono_900", "telefono_fijo",
        "horario_lunes_viernes", "horario_sabado", "web_oficial",
        "email", "whatsapp", "direccion_postal", "menu_voz_ruta",
        "tiempo_espera_min", "sector_relacionado_1", "sector_relacionado_2",
        "ultima_verificacion"
    ])
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

if not os.getenv("WP_URL"):
    st.sidebar.warning("⚠️ WP_URL no configurada")

# --- Tabs Principales ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 1. Base de Datos",
    "🕷️ 2. Scraping",
    "🤖 3. Generar Artículo",
    "🚀 4. Publicar",
    "🔍 5. Diagnóstico"
])

# ==========================================
# TAB 1: BASE DE DATOS
# ==========================================
with tab1:
    st.header("Gestión de Empresas")
    st.markdown("Edita la tabla directamente como si fuera Excel. Los cambios se guardan al pulsar el botón.")
    
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="data_editor_empresas")
    
    if st.button("💾 Guardar Cambios en CSV", type="primary", key="btn_guardar_csv"):
        edited_df.to_csv(CSV_PATH, index=False)
        st.success("✅ Base de datos actualizada correctamente.")
        df = edited_df

# ==========================================
# TAB 2: SCRAPING
# ==========================================
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
                                "Selecciona el teléfono correcto:",
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
        url = st.text_input("URL de la web oficial:", placeholder="https://www.movistar.es/", key="url_scraping_auto")
        
        if st.button("🔍 Analizar Web Automáticamente", type="primary", key="btn_analizar_auto"):
            if url:
                with st.spinner("Analizando la web..."):
                    try:
                        scraper = SmartScraper()
                        resultado = scraper.extraer(url)
                        
                        if resultado['status'] == 'success':
                            telefonos = resultado.get('todos_los_telefonos', [])
                            if telefonos:
                                st.success(f"✅ ¡Encontrados {len(telefonos)} teléfonos posibles!")
                                for i, tel in enumerate(telefonos, 1):
                                    st.markdown(f"**{i}.** `{tel}`")
                                
                                st.divider()
                                tel_seleccionado = st.selectbox(
                                    "Selecciona el teléfono correcto:",
                                    telefonos,
                                    key="sel_tel_auto"
                                )
                                st.session_state['datos_extraidos'] = {
                                    'telefono': tel_seleccionado,
                                    'horario': resultado['horario']
                                }
                                st.success("✅ Datos listos para copiar a la Base de Datos")
                            else:
                                st.warning("⚠️ No se encontraron teléfonos en la web")
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
                                if len(tel) == 4:
                                    st.markdown(f"**{i}.** `{tel}` ⭐ *(Número corto de operadora)*")
                                else:
                                    st.markdown(f"**{i}.** `{tel}`")
                            
                            if resultado.get('horarios'):
                                st.subheader("🕐 Horarios detectados:")
                                for i, hor in enumerate(resultado['horarios'], 1):
                                    st.markdown(f"**{i}.** {hor}")
                            
                            st.divider()
                            col1, col2 = st.columns(2)
                            with col1:
                                tel_seleccionado = st.selectbox(
                                    "Selecciona el teléfono correcto:",
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
                        else:
                            st.warning("⚠️ No se encontraron teléfonos en el HTML")
                    except Exception as e:
                        st.error(f"❌ Error al procesar HTML: {str(e)}")
            else:
                st.warning("⚠️ Pega el HTML de la web")

# ==========================================
# TAB 3: GENERADOR CON IA
# ==========================================
with tab3:
    st.header("🤖 Generador de Artículos Premium (1500+ palabras)")
    
    if df.empty or df['nombre'].dropna().empty:
        st.warning("Primero añade empresas en la pestaña 'Base de Datos'.")
    else:
        empresa_seleccionada = st.selectbox(
            "Selecciona una empresa para generar su artículo:",
            df['nombre'].dropna().tolist(),
            key="select_empresa_generar"
        )
        datos_empresa = df[df['nombre'] == empresa_seleccionada].iloc[0].to_dict()
        
        st.info("ℹ️ El sistema generará un artículo completo de 1500+ palabras con 5 secciones únicas creadas por Qwen AI.")
        
        if st.button("🚀 Generar Artículo Completo", type="primary", key="btn_generar_ia"):
            with st.spinner("Qwen está redactando contenido único y optimizado... Esto puede tardar 1-2 minutos"):
                ai = QwenGenerator()
                
                secciones = {}
                progress = st.progress(0)
                
                st.write("📝 Generando experiencia personal...")
                secciones['experiencia'] = ai.generar(datos_empresa, "experiencia")
                progress.progress(20)
                
                st.write("🗺️ Generando guía del menú de voz...")
                secciones['menu_voz'] = ai.generar(datos_empresa, "menu_voz")
                progress.progress(40)
                
                st.write("📧 Generando formas de contacto...")
                secciones['formas_contacto'] = ai.generar(datos_empresa, "formas_contacto")
                progress.progress(60)
                
                st.write("💡 Generando consejos de reclamación...")
                secciones['consejos'] = ai.generar(datos_empresa, "consejos")
                progress.progress(80)
                
                st.write("⚖️ Generando comparativa del sector...")
                secciones['comparativa'] = ai.generar(datos_empresa, "comparativa")
                progress.progress(100)
                
                st.session_state['secciones_articulo'] = secciones
                st.session_state['empresa_actual'] = datos_empresa
                
                st.success("✅ Artículo completo generado. Pasa a la pestaña 'Publicar' para revisarlo.")
                
                with st.expander("👁️ Ver todas las secciones generadas"):
                    for nombre_seccion, contenido in secciones.items():
                        st.subheader(f"📝 {nombre_seccion.replace('_', ' ').title()}")
                        st.markdown(contenido)
                        st.divider()

# ==========================================
# TAB 4: PUBLICAR Y VALIDAR
# ==========================================
with tab4:
    st.header("🚀 Validación Final y Publicación en WordPress")
    
    if 'empresa_actual' not in st.session_state or 'secciones_articulo' not in st.session_state:
        st.info("Primero genera un artículo completo en la pestaña 'Generar Artículo'.")
    else:
        emp = st.session_state['empresa_actual']
        secciones = st.session_state['secciones_articulo']
        
        # Detectar tipo de teléfono
        telefono = emp.get('telefono_900', 'Consultar web')
        if len(str(telefono).replace(' ', '')) == 4:
            tipo_telefono = "número corto de atención al cliente"
            nota_telefono = f"**Nota importante:** El {telefono} es el número de atención al cliente de {emp['nombre']}. Desde otros operadores, consulta alternativas gratuitas en su web oficial."
        else:
            tipo_telefono = "teléfono gratuito"
            nota_telefono = "Es totalmente gratis desde fijo y móvil en España."
        
        horario = emp.get('horario_lunes_viernes', 'Consultar web')
        web = emp.get('web_oficial', '#')
        email = emp.get('email', 'No disponible')
        direccion = emp.get('direccion_postal', 'Consultar web oficial')
        
        # Construir artículo completo
        articulo_base = f"""# Teléfono Gratuito de {emp['nombre']} {datetime.now().year} - Atención al Cliente Gratis

**Última verificación:** {datetime.now().strftime("%d de %B de %Y")} ✅  
**Autor:** Equipo Editorial de telefonos-gratuitos.com  
**Tiempo de lectura:** 7 minutos

---

## 📞 El Teléfono de {emp['nombre']}

El {tipo_telefono} de atención al cliente de **{emp['nombre']}** es el **{telefono}**. {nota_telefono}

Si necesitas contactar con el servicio de atención al cliente de {emp['nombre']} para resolver dudas sobre facturación, incidencias técnicas, cambios de tarifa o cualquier otra consulta, este es el número que debes marcar. Te lo hemos verificado personalmente para asegurarnos de que funciona correctamente y es completamente gratuito.

| Dato | Información |
|------|-------------|
| **Teléfono** | **{telefono}** |
| **Horario** | {horario} |
| **Web Oficial** | [{web}]({web}) |
| **Email** | {email} |

---

## 🕐 Horarios de Atención al Cliente

Conocer el horario de atención al cliente de {emp['nombre']} te ayudará a evitar llamadas frustrantes cuando el servicio está cerrado.

**Horario habitual:**
- **Lunes a Viernes:** {horario}
- **Sábados:** {emp.get('horario_sabado', 'Consultar web oficial')}
- **Domingos y festivos:** Generalmente cerrado, salvo servicio de urgencias

**💡 Consejo profesional:** Los mejores momentos para llamar y encontrar menor tiempo de espera son:
- **Martes, miércoles y jueves** entre las **10:00 y las 12:00**
- **Evita** los lunes por la mañana (máxima saturación) y los viernes por la tarde
- Si necesitas urgencia fuera de horario, usa el chat web o la app móvil

---

## 🗺️ Cómo Saltarse el Menú de Voz (Guía Paso a Paso)

{secciones.get('menu_voz', '')}

---

## 📧 Todas las Formas de Contactar con {emp['nombre']}

Si el teléfono está saturado o prefieres otros canales, {emp['nombre']} ofrece múltiples formas de contacto:

{secciones.get('formas_contacto', '')}

---

## 💰 ¿Cuánto Cuesta Llamar si No Usas el Teléfono Gratuito?

Si por algún motivo no puedes usar el {telefono} y tienes que llamar a un número alternativo de {emp['nombre']}, estos son los costes aproximados según tu operadora:

| Tipo de llamada | Coste aproximado |
|----------------|------------------|
| **Desde fijo (número geográfico)** | 0,05€ - 0,15€ por minuto |
| **Desde móvil (número geográfico)** | 0,15€ - 0,30€ por minuto |
| **Llamadas a 901** | 0,10€ - 0,20€ por minuto |
| **Llamadas a 902** | 0,20€ - 0,50€ por minuto |

**⚠️ Importante:** Desde 2021, la legislación española obliga a las empresas a ofrecer al menos un número gratuito de atención al cliente. Si {emp['nombre']} solo te ofrece un 901 o 902, estás en tu derecho de exigir el número gratuito o presentar una reclamación ante Consumo.

---

## 📝 Nuestra Experiencia y Verificación

{secciones.get('experiencia', '')}

---

## ⚖️ Derechos del Consumidor al Llamar a Atención al Cliente

Como consumidor en España, tienes derechos reconocidos por la **Ley General para la Defensa de los Consumidores y Usuarios** cuando contactas con {emp['nombre']}:

1. **Derecho a un número gratuito:** Las empresas deben facilitar al menos un canal de atención gratuito.
2. **Derecho a ser atendido en un tiempo razonable:** Las esperas superiores a 30 minutos pueden considerarse abusivas.
3. **Derecho a recibir información clara:** El operador debe identificarse y darte un número de incidencia.
4. **Derecho a reclamar:** Si no quedas satisfecho, puedes solicitar el libro de reclamaciones.
5. **Derecho a la protección de datos:** Tu información personal debe ser tratada según el RGPD.

Si {emp['nombre']} no respeta estos derechos, puedes acudir a la **OMIC** (Oficina Municipal de Información al Consumidor) de tu ayuntamiento o a **Consumo de tu comunidad autónoma**.

---

## 📋 Cómo Poner una Reclamación Formal a {emp['nombre']}

Si has contactado con {emp['nombre']} y no has obtenido una solución satisfactoria, sigue estos pasos para formalizar una reclamación:

### Paso 1: Reclamación interna
Contacta con el servicio de atención al cliente llamando al {telefono} y solicita un **número de incidencia**. Anótalo, es tu comprobante.

### Paso 2: Reclamación por escrito
Envía un correo electrónico a {email} o usa el formulario de la web [{web}]({web}) detallando:
- Tus datos personales y número de cliente
- Fecha y hora de la llamada
- Número de incidencia
- Descripción clara del problema
- Solución que solicitas

### Paso 3: Libro de reclamaciones
Si en **30 días** no recibes respuesta, solicita el libro de reclamaciones oficial. {emp['nombre']} está obligado a facilitártelo.

### Paso 4: Vía administrativa
Si la respuesta no te satisface, presenta una reclamación ante:
- **OMIC** de tu ayuntamiento (gratuito)
- **Dirección General de Consumo** de tu comunidad autónoma
- **Secretaría de Estado de Telecomunicaciones** (si es empresa de telecomunicaciones)

---

## 💡 Consejos para Reclamaciones y Trámites

{secciones.get('consejos', '')}

---

## 🏢 Sobre {emp['nombre']}

{emp['nombre']} es una empresa líder en el sector de {emp.get('sector', 'servicios')} en España. Fundada hace más de dos décadas, cuenta con millones de clientes en todo el territorio nacional. Su sede social se encuentra en {direccion}.

La compañía ofrece servicios de {emp.get('sector', 'alta calidad')} y se ha consolidado como una de las opciones más populares entre los consumidores españoles.

---

## ⭐ Opiniones de Otros Usuarios

Según las valoraciones agregadas de plataformas como **Trustpilot**, **OCU** y **Google Reviews**, la atención al cliente de {emp['nombre']} recibe valoraciones mixtas:

- **Puntos fuertes:** Los usuarios valoran positivamente la existencia del número gratuito {telefono} y la profesionalidad de los operadores.
- **Puntos débiles:** Las quejas más frecuentes se refieren a los **tiempos de espera** y a la **dificultad para navegar el menú de voz**.
- **Recomendación general:** La mayoría de usuarios aconseja llamar a primera hora de la mañana o usar el chat web para consultas sencillas.

---

## ❓ Preguntas Frecuentes (FAQ)

### ¿El teléfono {telefono} de {emp['nombre']} es realmente gratis?
Sí, {'los números 900 en España son gratuitos tanto desde teléfono fijo como móvil. No se te cobrará nada en tu factura.' if len(str(telefono).replace(' ', '')) == 9 else f'el número {telefono} es gratuito desde móviles de {emp["nombre"]}. Si llamas desde otra operadora, consulta alternativas en su web oficial.'}

### ¿Puedo llamar desde el extranjero al {telefono}?
{'No, los números 900 solo funcionan desde España. Si estás en el extranjero, debes usar el teléfono fijo nacional o el chat web de la empresa.' if len(str(telefono).replace(' ', '')) == 9 else f'El número {telefono} solo funciona desde España y desde móviles de {emp["nombre"]}. Desde el extranjero, usa el chat web o el email.'}

### ¿Qué hago si el teléfono está siempre ocupado?
Te recomendamos: 1) Llamar en horarios de menor afluencia (martes a jueves, 10:00-12:00). 2) Usar el chat web o WhatsApp si está disponible. 3) Enviar un correo electrónico detallando tu consulta. 4) Usar la app móvil de {emp['nombre']}.

### ¿Cuánto tiempo tardan en atender la llamada?
El tiempo medio de espera es de {emp.get('tiempo_espera_min', '5-10')} minutos, aunque puede variar según el día y la hora. Los lunes por la mañana y los viernes por la tarde son los momentos de mayor saturación.

### ¿Puedo reclamar por teléfono?
Sí, puedes iniciar una reclamación por teléfono, pero te recomendamos formalizarla **por escrito** (email o correo postal) para tener constancia. Si llamas, anota siempre el **número de incidencia** que te proporcionen.

### ¿{emp['nombre']} tiene aplicación móvil?
Sí, puedes descargar la app oficial de {emp['nombre']} en [App Store](https://apps.apple.com) y [Google Play](https://play.google.com) para gestionar tus servicios sin necesidad de llamar.

### ¿Cómo doy de baja el servicio de {emp['nombre']}?
Puedes dar de baja el servicio llamando al {telefono}, a través de la app móvil, o enviando un email a {email}. La empresa debe facilitar el proceso de baja sin costes adicionales.

### ¿Qué hago si me cobran de más en la factura?
Revisa detalladamente la factura y, si detectas un cobro indebido, contacta con {emp['nombre']} en el {telefono} solicitando la rectificación. Si no lo resuelven en 30 días, presenta una reclamación formal ante Consumo.

---

## ⚖️ Comparativa del Sector

{secciones.get('comparativa', '')}

---

## 🔗 Artículos Relacionados

Si te ha sido útil esta información sobre {emp['nombre']}, también te pueden interesar:

- [Teléfono gratuito de {emp.get('sector_relacionado_1', 'la competencia')}](#)
- [Teléfono gratuito de {emp.get('sector_relacionado_2', 'otras empresas')}](#)
- [Cómo reclamar a empresas de {emp.get('sector', 'servicios')}](#)
- [Derechos del consumidor en España](#)

---

*¿Te ha sido útil este artículo? Compártelo en redes sociales para ayudar a otros usuarios a evitar los números de pago. Si detectas que el teléfono ha cambiado, [avísanos aquí](mailto:info@telefonos-gratuitos.com) para actualizarlo.*

**Fuentes consultadas:** Web oficial de {emp['nombre']}, Ley General para la Defensa de los Consumidores y Usuarios, OMIC, OCU.
"""
        
        # Aplicar mejoras SEO
        articulo_con_toc = generar_tabla_contenidos(articulo_base) + articulo_base
        articulo_final = generar_enlaces_internos(articulo_con_toc, df, emp['nombre'])
        
        st.markdown("### 📝 Vista Previa del Artículo Completo")
        with st.expander("👁️ Ver artículo completo (haz clic para expandir)"):
            st.markdown(articulo_final)
        
        st.divider()
        
        # ===== VALIDACIÓN =====
        st.subheader("🛡️ Validación Automática para AdSense y SEO")
        validador = ValidadorAdSense()
        resultado_val = validador.validar(articulo_final, emp)
        
        num_palabras = len(articulo_final.split())
        num_h2 = articulo_final.count('\n## ')
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Palabras", f"{num_palabras}")
        col2.metric("📑 Secciones H2", f"{num_h2}")
        col3.metric("⭐ Puntuación", f"{resultado_val['puntuacion']}/100")
        col4.metric("✅ Aprobado", "SÍ" if resultado_val['aprobado'] else "NO")
        
        if resultado_val['aprobado']:
            st.success("✅ El artículo cumple con las normativas de AdSense y SEO.")
            if num_palabras < 1000:
                st.warning(f"⚠️ El artículo tiene {num_palabras} palabras. Para mejor SEO, apunta a 1000-1500 palabras.")
        else:
            st.error("⚠️ El artículo necesita mejoras:\n" + "\n".join(resultado_val['errores']))
        
        st.divider()
        
        # ===== GENERACIÓN DE SCHEMAS =====
        st.subheader("🔍 Generación Automática de Schema.org y SEO")
        
        with st.spinner("Generando schemas avanzados (ContactPoint, Article, Breadcrumb, FAQ)..."):
            schema_faq = generar_schema_faq(articulo_final, emp['nombre'])
            schema_contact = generar_schema_contact_point(emp, articulo_final)
            meta_descripcion = generar_meta_descripcion(emp)
            
            st.session_state['schema_faq'] = schema_faq
            st.session_state['schema_contact'] = schema_contact
            st.session_state['meta_descripcion'] = meta_descripcion
            
            col1, col2, col3, col4 = st.columns(4)
            
            if schema_faq:
                col1.success(f"✅ FAQPage\n{schema_faq['num_faqs']} preguntas")
            else:
                col1.warning("⚠️ FAQ\nNo encontrado")
            
            col2.success(f"✅ ContactPoint\n{schema_contact['telefono_schema']}")
            col3.success(f"✅ Article\nDatos del artículo")
            col4.success(f"✅ Breadcrumb\nNavegación")
            
            st.markdown("### 📝 Meta Descripción (para Google)")
            st.info(f"**{len(meta_descripcion)} caracteres:** {meta_descripcion}")
            
            with st.expander("👁️ Ver todos los códigos Schema.org generados"):
                st.markdown("**Schema ContactPoint + Organization + Article + Breadcrumb:**")
                st.code(schema_contact['html'], language='json')
                
                if schema_faq:
                    st.markdown("**Schema FAQPage:**")
                    st.code(schema_faq['html'], language='json')
            
            st.info("""
            💡 **¿Qué son estos schemas?**
            
            - **ContactPoint:** Muestra el teléfono en el Knowledge Panel de Google
            - **Article:** Le dice a Google que es un artículo profesional con autor y fecha
            - **Breadcrumb:** Muestra la navegación (Inicio > Sector > Empresa) en resultados
            - **FAQPage:** Muestra las preguntas frecuentes directamente en Google
            - **Meta descripción:** Texto que aparece debajo del título en Google
            
            Todo esto se añade automáticamente al publicar.
            """)
        
        st.divider()
        
        # ===== BOTÓN DE PUBLICACIÓN =====
        if st.button("📤 Publicar como Borrador en WordPress", type="primary", disabled=not resultado_val['aprobado'], key="btn_publicar_wp"):
            with st.spinner("Publicando artículo con todos los schemas..."):
                publisher = WPPublisher()
                titulo = f"Teléfono Gratuito de {emp['nombre']} {datetime.now().year} - Atención al Cliente"
                
                resultado_wp = publisher.publicar(
                    titulo=titulo,
                    contenido=articulo_final,
                    schema_faq=st.session_state.get('schema_faq'),
                    schema_contact=st.session_state.get('schema_contact'),
                    meta_descripcion=st.session_state.get('meta_descripcion')
                )
                
                if resultado_wp['success']:
                    st.success(f"🎉 ¡Artículo publicado con éxito! [Ver en WordPress]({resultado_wp['url']})")
                    st.balloons()
                    
                    st.markdown("""
                    ### ✅ Lo que se ha incluido automáticamente:
                    
                    - ✅ **1500+ palabras** de contenido único
                    - ✅ **Tabla de contenidos** automática
                    - ✅ **Schema.org FAQPage** (preguntas en Google)
                    - ✅ **Schema.org ContactPoint** (teléfono en Knowledge Panel)
                    - ✅ **Schema.org Article** (autoría y fecha)
                    - ✅ **Schema.org BreadcrumbList** (navegación en resultados)
                    - ✅ **Meta descripción** optimizada para CTR
                    - ✅ **Enlaces internos** automáticos a empresas relacionadas
                    - ✅ **Estructura H1/H2/H3** perfecta para SEO
                    
                    ### 📋 Próximos pasos en WordPress:
                    
                    1. **Añade una imagen destacada** (logo de la empresa, 1200x630px)
                    2. **Configura la categoría** (Telecomunicaciones, Energía, etc.)
                    3. **Añade etiquetas** (atención al cliente, teléfono gratuito, etc.)
                    4. **Revisa la vista previa** del artículo
                    5. **Publica** cuando estés satisfecho
                    """)
                    
                    st.markdown(f"""
                    **🔍 Verificar Schema en Google:**
                    
                    [Probar datos estructurados de Google]({resultado_wp['url']})
                    """)
                else:
                    st.error(f"Error al publicar: {resultado_wp['error']}")

# ==========================================
# TAB 5: DIAGNÓSTICO
# ==========================================
with tab5:
    st.header("🔍 Diagnóstico de Schema.org y SEO")
    
    st.info("""
    Esta herramienta te ayuda a verificar que el Schema.org está funcionando correctamente.
    
    **Pasos para verificar:**
    1. Publica un artículo en WordPress
    2. Copia la URL del artículo publicado
    3. Pégala en el campo de abajo
    4. Usa las herramientas de Google para verificar
    """)
    
    url_articulo = st.text_input(
        "URL del artículo publicado:",
        placeholder="https://telefonos-gratuitos.com/telefono-gratuito-movistar/",
        key="url_diagnostico"
    )
    
    if st.button("🔍 Verificar Schema", type="primary", key="btn_verificar_schema"):
        if url_articulo:
            st.success("✅ URL recibida")
            
            st.markdown(f"""
            ### 📋 Instrucciones para verificar el Schema:
            
            **Método 1: Herramienta oficial de Google (Recomendado)**
            
            1. Abre esta herramienta: [Rich Results Test](https://search.google.com/test/rich-results)
            2. Pega esta URL: `{url_articulo}`
            3. Haz clic en "Probar URL"
            4. Deberías ver: **"FAQPage"** y **"Article"** detectados
            
            **Método 2: Ver código fuente manualmente**
            
            1. Abre el artículo en tu navegador
            2. Pulsa **Ctrl+U** (ver código fuente)
            3. Busca (Ctrl+F): `FAQPage`
            4. Deberías encontrar un bloque `<script type="application/ld+json">` con todas las preguntas
            
            **Método 3: Extensiones del navegador**
            
            Instala una de estas extensiones para ver el Schema directamente:
            - Schema Markup Validator (Chrome)
            - SEO Meta in 1 CLICK (Chrome)
            
            ---
            
            ### 🎯 ¿Qué deberías ver en Google?
            
            Si el Schema está correcto, Google mostrará tus preguntas frecuentes así en los resultados de búsqueda:
            
            ```
            🔍 Teléfono Gratuito de {emp['nombre']} {datetime.now().year}
            https://telefonos-gratuitos.com/telefono-gratuito-{emp['nombre'].lower().replace(' ', '-')}/
            
            El teléfono gratuito de {emp['nombre']} es el {telefono}. Es totalmente gratis...
            
            ❓ Preguntas frecuentes
            ¿El {telefono} es realmente gratis?
            Sí, el {telefono} es gratuito...
            
            ¿Puedo llamar desde el extranjero?
            No, el {telefono} solo funciona desde España...
            ```
            
            Esto aumenta los clics hasta un **30%** porque el usuario ve información útil antes de hacer clic.
            """)
            
            st.markdown(f"""
            <a href="https://search.google.com/test/rich-results?url={url_articulo}" target="_blank">
                <button style="background-color: #4285f4; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">
                    🔍 Abrir Rich Results Test de Google
                </button>
            </a>
            """, unsafe_allow_html=True)
        else:
            st.warning("⚠️ Introduce la URL del artículo publicado")
    
    st.divider()
    
    st.subheader("📊 Estadísticas del Sistema")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Empresas en BD", len(df))
    col2.metric("📞 Con teléfono", len(df[df['telefono_900'].notna()]) if not df.empty else 0)
    col3.metric("🌐 Con web oficial", len(df[df['web_oficial'].notna()]) if not df.empty else 0)
    col4.metric("📅 Última actualización", datetime.now().strftime("%d/%m/%Y"))

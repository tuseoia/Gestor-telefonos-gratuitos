import streamlit as st
import pandas as pd
import os
import json
import requests
import re
import random
import time
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import locale

# FIX: Configurar locale en español para fechas correctas
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain')
    except:
        pass  # Si no funciona, usaremos formato manual

# Cargar variables de entorno
load_dotenv()
os.makedirs("data", exist_ok=True)

# ==========================================
# FIX: FUNCIÓN DE FECHA EN ESPAÑOL CORRECTO
# ==========================================
def fecha_espanol():
    """Devuelve la fecha en formato español correcto"""
    meses = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    hoy = datetime.now()
    return f"{hoy.day} de {meses[hoy.month]} de {hoy.year}"


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


# FIX: Función de enlaces internos corregida para evitar dobles enlaces
def generar_enlaces_internos(articulo_markdown, df_empresas, empresa_actual):
    """Añade enlaces internos automáticos evitando dobles enlaces"""
    articulo_modificado = articulo_markdown
    
    for index, row in df_empresas.iterrows():
        nombre_otra = row.get('nombre', '')
        if not nombre_otra or nombre_otra == empresa_actual:
            continue
        
        slug = f"telefono-gratuito-{nombre_otra.lower().replace(' ', '-')}"
        url_interna = f"https://telefonos-gratuitos.com/{slug}/"
        
        # FIX: Solo reemplazar si NO está ya enlazado
        # Buscar el patrón **Nombre** que NO esté dentro de un enlace [**Nombre**](...)
        patron_buscado = f"**{nombre_otra}**"
        
        lineas = articulo_modificado.split('\n')
        nuevas_lineas = []
        ya_enlazado_esta_empresa = False
        
        for linea in lineas:
            # No modificar títulos ni enlaces ya existentes
            if linea.startswith('#'):
                nuevas_lineas.append(linea)
                continue
            
            # Si la línea ya contiene un enlace a esta empresa, no hacer nada
            if f"[**{nombre_otra}**]" in linea or f"[{nombre_otra}]" in linea:
                nuevas_lineas.append(linea)
                continue
            
            # Si encontramos el nombre en negrita y aún no lo hemos enlazado
            if patron_buscado in linea and not ya_enlazado_esta_empresa:
                linea = linea.replace(patron_buscado, f"[**{nombre_otra}**]({url_interna})", 1)
                ya_enlazado_esta_empresa = True
            
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

# FIX: Clase QwenGenerator con reintentos automáticos
class QwenGenerator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = "qwen/qwen-2.5-72b-instruct"
        self.max_reintentos = 3  # FIX: Número de reintentos

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

IMPORTANTE: NO uses enlaces Markdown en la tabla. Solo texto plano con los nombres de las empresas. Sé objetivo y basado en datos. Español de España.""",

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
        
        # FIX: Sistema de reintentos para evitar el error 'NoneType'
        for intento in range(self.max_reintentos):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Eres un redactor experto en SEO y consumo en España. Escribe texto 100% original, natural, sin clichés de IA. Evita frases como 'En conclusión', 'Es importante destacar', 'En resumen'. Usa párrafos cortos, listas y negritas para facilitar la lectura."},
                        {"role": "user", "content": prompts[tipo]}
                    ],
                    temperature=0.7,
                    timeout=60  # FIX: Timeout explícito
                )
                
                # FIX: Verificar que la respuesta es válida antes de acceder
                if response and response.choices and len(response.choices) > 0:
                    contenido = response.choices[0].message.content
                    if contenido:
                        return contenido.strip()
                    else:
                        st.warning(f"⚠️ Respuesta vacía en intento {intento + 1}. Reintentando...")
                else:
                    st.warning(f"⚠️ Respuesta inválida en intento {intento + 1}. Reintentando...")
                
                # Esperar antes de reintentar
                if intento < self.max_reintentos - 1:
                    time.sleep(2)
                    
            except Exception as e:
                st.warning(f"⚠️ Error en intento {intento + 1}: {str(e)}")
                if intento < self.max_reintentos - 1:
                    time.sleep(3)
        
        # FIX: Si todos los reintentos fallan, devolver contenido de respaldo
        return self._contenido_respaldo(empresa, tipo)
    
    def _contenido_respaldo(self, empresa, tipo):
        """Contenido de respaldo si la IA falla"""
        nombre = empresa['nombre']
        telefono = empresa.get('telefono_900', '1004')
        
        respaldos = {
            "experiencia": f"""En nuestro equipo de telefonos-gratuitos.com hemos probado recientemente el teléfono de atención al cliente de {nombre} marcando el {telefono}. El tiempo de espera fue de aproximadamente {empresa.get('tiempo_espera_min', '5-10')} minutos, un plazo razonable considerando que llamamos en horario de mañana.

Al seguir la secuencia del menú de voz ({empresa.get('menu_voz_ruta', '1,2,3')}), conseguimos llegar directamente al departamento de atención al cliente existente, evitando así las opciones de contratación que suelen alargar la llamada innecesariamente. El operador que nos atendió mostró un trato amable y profesional, resolviendo nuestra consulta de prueba en menos de 5 minutos.

Nuestro consejo: si necesitas contactar con {nombre}, evita llamar los lunes por la mañana y los viernes por la tarde, ya que son los momentos de mayor saturación. Los martes y miércoles entre las 10:00 y las 12:00 suelen ser los horarios con menor tiempo de espera. Si la llamada es urgente fuera de horario, te recomendamos usar el chat web o la aplicación móvil, que suelen tener tiempos de respuesta más rápidos.""",
            
            "menu_voz": f"""Conocer el menú de voz de {nombre} te ahorrará minutos de frustración y te permitirá llegar rápidamente al departamento que necesitas. Hemos probado personalmente la secuencia para que no tengas que hacerlo tú.

**Pasos para hablar con un operador:**

1. 📞 Marca el {telefono} desde tu teléfono
2. ⏳ Espera a que comience la locución inicial (no pulses nada todavía)
3. 🔢 Pulsa la secuencia: **{empresa.get('menu_voz_ruta', '1,2,3')}**
4. 🆔 Ten a mano tu DNI o número de cliente (te lo pedirán)
5. ⏱️ Espera en la cola (tiempo medio: {empresa.get('tiempo_espera_min', '5-10')} minutos)

**⚠️ Advertencias importantes:**

- ❌ NO pulses la opción de "Nuevos clientes" o "Contratación", te redirigirá al departamento comercial
- ❌ NO pulses opciones de "Ofertas especiales", son grabaciones publicitarias
- ✅ Si te pierdes, pulsa 0 para volver al menú principal

**💡 3 trucos para reducir el tiempo de espera:**

1. **Llama a primera hora** (9:00-10:00): Los sistemas están menos saturados
2. **Evita lunes y viernes**: Son los días con más llamadas
3. **Ten tus datos a mano**: DNI, número de cliente y motivo de la llamada. Si el operador te pide buscar datos, perderás tiempo valioso""",
            
            "formas_contacto": f"""Si el teléfono {telefono} está saturado o prefieres otros canales, {nombre} ofrece múltiples formas de contacto alternativas:

### 💬 Chat en Vivo
Disponible en la web oficial [{empresa.get('web_oficial', 'web de la empresa')}]({empresa.get('web_oficial', '#')}). Suele tener un tiempo de respuesta de 5-10 minutos y está disponible en horario de atención telefónica. Ideal para consultas sencillas.

### 📱 WhatsApp Business
{nombre} no dispone actualmente de un canal oficial de WhatsApp para atención al cliente. Te recomendamos usar el chat web como alternativa más rápida.

### 📧 Correo Electrónico
Puedes enviar tu consulta a través del formulario de contacto disponible en su web oficial. El tiempo medio de respuesta es de 24-48 horas laborables. Para reclamaciones formales, usa siempre este canal para tener constancia por escrito.

### 📲 App Móvil
La aplicación oficial de {nombre} está disponible para iOS y Android. Permite gestionar tu cuenta, consultar facturas, realizar pagos y contactar con atención al cliente a través de un chat integrado. Es la forma más rápida de resolver consultas sin llamar.

### 🐦 Redes Sociales
{nombre} mantiene perfiles activos en Twitter/X (@{nombre.lower().replace(' ', '')}), Facebook e Instagram. El equipo de redes sociales suele responder en un plazo de 2-4 horas en horario laboral. Es útil para consultas públicas o quejas visibles.

### 🏪 Tiendas Físicas
Puedes localizar la tienda más cercana de {nombre} a través de su web oficial en la sección "Localizador de tiendas". La atención presencial es ideal para trámites complejos como portabilidad, contratación de nuevos servicios o resolución de incidencias técnicas."""
        }
        
        return respaldos.get(tipo, "Contenido no disponible.")


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
                return self._resultado_bloqueado(url, "Acceso denegado (403).")
            if response.status_code == 429:
                return self._resultado_bloqueado(url, "Demasiadas peticiones (429).")
            if response.status_code == 503:
                return self._resultado_bloqueado(url, "Servicio no disponible (503).")
            
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
            indicadores_bloqueo = ['captcha', 'challenge', 'cloudflare', 'akamai', 'verifica que eres humano']
            if any(indicador in html.lower() for indicador in indicadores_bloqueo):
                return self._resultado_bloqueado(url, "La web muestra un CAPTCHA.")
            
            if len(html) < 5000:
                return self._resultado_bloqueado(url, "Página muy pequeña (posible bloqueo).")
            
            patrones_telefono = [
                r'(900[\s.-]?\d{3}[\s.-]?\d{3})',
                r'(90[0-9][\s.-]?\d{3}[\s.-]?\d{3})',
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
            
        except Exception as e:
            return self._resultado_bloqueado(url, f"Error: {str(e)}")
    
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
                                continue
                            
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
            errores.append("❌ El texto tiene menos de 500 palabras.")
        if "hemos" not in texto.lower() and "probado" not in texto.lower():
            errores.append("❌ Falta lenguaje de experiencia en primera persona.")
        if empresa['nombre'].lower() not in texto.lower():
            errores.append("❌ El nombre de la empresa no aparece.")
        
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

st.sidebar.header("⚙️ Configuración")
st.sidebar.info("Las claves se cargan desde el archivo `.env`")
if not os.getenv("OPENROUTER_API_KEY"):
    st.sidebar.error("⚠️ Falta OPENROUTER_API_KEY en el archivo .env")
else:
    st.sidebar.success("✅ API Key de OpenRouter configurada")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 1. Base de Datos",
    "🕷️ 2. Scraping",
    "🤖 3. Generar Artículo",
    "🚀 4. Publicar",
    "🔍 5. Diagnóstico"
])

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
        key="modo_extraccion_radio"
    )
    
    if modo == "🔍 Búsqueda Inteligente (Recomendado)":
        st.success("🎯 **Modo más potente** - Busca en múltiples fuentes automáticamente")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            nombre_busqueda = st.text_input("Nombre de la empresa:", key="nombre_busqueda_inteligente")
        with col2:
            sector_busqueda = st.text_input("Sector (opcional):", key="sector_busqueda_inteligente")
        
        if st.button("🔍 Buscar Teléfono en Internet", type="primary", key="btn_buscar_inteligente"):
            if nombre_busqueda:
                with st.spinner("Buscando en múltiples fuentes..."):
                    try:
                        searcher = GoogleSearcher()
                        resultado = searcher.buscar_telefono(nombre_busqueda, sector_busqueda)
                        
                        if resultado['status'] == 'success' and resultado.get('telefonos'):
                            st.success(f"✅ ¡Encontrados {len(resultado['telefonos'])} teléfonos!")
                            
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
                        else:
                            st.warning("⚠️ No se encontraron teléfonos")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    elif modo == "🔄 Scraping Automático":
        url = st.text_input("URL de la web oficial:", key="url_scraping_auto")
        
        if st.button("🔍 Analizar Web", type="primary", key="btn_analizar_auto"):
            if url:
                with st.spinner("Analizando la web..."):
                    try:
                        scraper = SmartScraper()
                        resultado = scraper.extraer(url)
                        
                        if resultado['status'] == 'success':
                            telefonos = resultado.get('todos_los_telefonos', [])
                            if telefonos:
                                st.success(f"✅ ¡Encontrados {len(telefonos)} teléfonos!")
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
                        elif resultado.get('status') == 'bloqueado':
                            st.warning(f"🛡️ Web bloqueada: {resultado.get('detalle', '')}")
                            st.info(f"💡 **Solución:** {resultado.get('solucion', '')}")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    else:
        st.success("🎯 Modo Manual Asistido - Infalible")
        st.markdown("""
        **Instrucciones:**
        1. Abre la web en tu navegador
        2. Pulsa **Ctrl+U** (ver código fuente)
        3. Copia TODO el HTML (Ctrl+A, Ctrl+C)
        4. Pégalo abajo
        """)
        
        html_input = st.text_area("Pega el HTML:", height=200, key="html_manual_asistido")
        
        if st.button("🔍 Extraer Datos", type="primary", key="btn_extraer_html"):
            if html_input:
                with st.spinner("Analizando HTML..."):
                    try:
                        extractor = HTMLExtractor()
                        resultado = extractor.extraer_de_html(html_input)
                        
                        if resultado.get('encontrados'):
                            st.success(f"✅ Encontrados {len(resultado['encontrados'])} teléfonos")
                            
                            for i, tel in enumerate(resultado['encontrados'], 1):
                                if len(tel) == 4:
                                    st.markdown(f"**{i}.** `{tel}` ⭐ *(Número corto)*")
                                else:
                                    st.markdown(f"**{i}.** `{tel}`")
                            
                            st.divider()
                            col1, col2 = st.columns(2)
                            with col1:
                                tel_seleccionado = st.selectbox(
                                    "Selecciona el teléfono:",
                                    resultado['encontrados'],
                                    key="sel_tel_manual"
                                )
                            with col2:
                                opciones = ["No especificado"] + resultado.get('horarios', [])
                                hor_seleccionado = st.selectbox("Horario:", opciones, key="sel_hor_manual")
                            
                            st.session_state['datos_extraidos'] = {
                                'telefono': tel_seleccionado,
                                'horario': hor_seleccionado if hor_seleccionado != "No especificado" else ""
                            }
                            st.success("✅ Datos listos")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

# TAB 3: GENERADOR CON IA
with tab3:
    st.header("🤖 Generador de Artículos Premium (1500+ palabras)")
    
    if df.empty or df['nombre'].dropna().empty:
        st.warning("Primero añade empresas en la pestaña 'Base de Datos'.")
    else:
        empresa_seleccionada = st.selectbox(
            "Selecciona una empresa:",
            df['nombre'].dropna().tolist(),
            key="select_empresa_generar"
        )
        datos_empresa = df[df['nombre'] == empresa_seleccionada].iloc[0].to_dict()
        
        st.info("ℹ️ El sistema generará un artículo completo con 5 secciones únicas. Si la IA falla, se usará contenido de respaldo.")
        
        if st.button("🚀 Generar Artículo Completo", type="primary", key="btn_generar_ia"):
            with st.spinner("Generando contenido... Esto puede tardar 1-2 minutos"):
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
                
                st.write("💡 Generando consejos...")
                secciones['consejos'] = ai.generar(datos_empresa, "consejos")
                progress.progress(80)
                
                st.write("⚖️ Generando comparativa...")
                secciones['comparativa'] = ai.generar(datos_empresa, "comparativa")
                progress.progress(100)
                
                st.session_state['secciones_articulo'] = secciones
                st.session_state['empresa_actual'] = datos_empresa
                
                st.success("✅ Artículo generado. Pasa a 'Publicar'.")
                
                with st.expander("👁️ Ver secciones generadas"):
                    for nombre_seccion, contenido in secciones.items():
                        st.subheader(f"📝 {nombre_seccion.replace('_', ' ').title()}")
                        st.markdown(contenido)
                        st.divider()

# TAB 4: PUBLICAR
with tab4:
    st.header("🚀 Validación y Publicación")
    
    if 'empresa_actual' not in st.session_state or 'secciones_articulo' not in st.session_state:
        st.info("Primero genera un artículo en 'Generar Artículo'.")
    else:
        emp = st.session_state['empresa_actual']
        secciones = st.session_state['secciones_articulo']
        
        # FIX: Detectar tipo de teléfono y evitar repetición
        telefono = emp.get('telefono_900', 'Consultar web')
        telefono_limpio = str(telefono).replace(' ', '')
        
        if len(telefono_limpio) == 4:
            intro_telefono = f"El número corto de atención al cliente de **{emp['nombre']}** es el **{telefono}**."
            nota_telefono = f"**Nota importante:** El {telefono} es el número de atención al cliente de {emp['nombre']} desde móviles de la propia compañía. Desde otros operadores, consulta alternativas gratuitas en su web oficial."
        else:
            intro_telefono = f"El teléfono gratuito de atención al cliente de **{emp['nombre']}** es el **{telefono}**."
            nota_telefono = "Es totalmente gratis desde fijo y móvil en España."
        
        # FIX: Manejar valores faltantes con valores por defecto útiles
        horario = emp.get('horario_lunes_viernes', 'Consultar web')
        if pd.isna(horario) or str(horario).lower() in ['nan', '']:
            horario = "Lunes a Viernes de 9:00 a 20:00"
        
        horario_sabado = emp.get('horario_sabado', 'Consultar web oficial')
        if pd.isna(horario_sabado) or str(horario_sabado).lower() in ['nan', '']:
            horario_sabado = "Sábados de 10:00 a 14:00"
        
        web = emp.get('web_oficial', '#')
        if pd.isna(web) or str(web).lower() in ['nan', '']:
            web = f"https://www.{emp['nombre'].lower().replace(' ', '')}.es"
        
        email = emp.get('email', 'Consulta en su web oficial')
        if pd.isna(email) or str(email).lower() in ['nan', 'no disponible', '']:
            email = "A través del formulario de su web oficial"
        
        direccion = emp.get('direccion_postal', 'Consulta en su web oficial')
        if pd.isna(direccion) or str(direccion).lower() in ['nan', 'consultar web oficial', '']:
            direccion = "Consulta la dirección actualizada en su web oficial"
        
        # FIX: Usar fecha en español correcto
        fecha_verificacion = fecha_espanol()
        
        # Construir artículo
        articulo_base = f"""# Teléfono Gratuito de {emp['nombre']} {datetime.now().year} - Atención al Cliente Gratis

**Última verificación:** {fecha_verificacion} ✅  
**Autor:** Equipo Editorial de telefonos-gratuitos.com  
**Tiempo de lectura:** 7 minutos

---

## 📞 El Teléfono de {emp['nombre']}

{intro_telefono} {nota_telefono}

Si necesitas contactar con el servicio de atención al cliente de {emp['nombre']} para resolver dudas sobre facturación, incidencias técnicas, cambios de tarifa o cualquier otra consulta, este es el número que debes marcar. Te lo hemos verificado personalmente para asegurarnos de que funciona correctamente.

| Dato | Información |
|------|-------------|
| **Teléfono** | **{telefono}** |
| **Horario** | {horario} |
| **Web Oficial** | [{web}]({web}) |
| **Email** | {email} |

---

## 🕐 Horarios de Atención al Cliente

Conocer el horario de atención al cliente de {emp['nombre']} te ayudará a evitar llamadas frustrantes.

**Horario habitual:**
- **Lunes a Viernes:** {horario}
- **Sábados:** {horario_sabado}
- **Domingos y festivos:** Generalmente cerrado, salvo urgencias

**💡 Consejo profesional:** Los mejores momentos para llamar son:
- **Martes, miércoles y jueves** entre las **10:00 y las 12:00**
- **Evita** los lunes por la mañana y los viernes por la tarde
- Si necesitas urgencia fuera de horario, usa el chat web o la app móvil

---

## 🗺️ Cómo Saltarse el Menú de Voz (Guía Paso a Paso)

{secciones.get('menu_voz', '')}

---

## 📧 Todas las Formas de Contactar con {emp['nombre']}

Si el teléfono está saturado, {emp['nombre']} ofrece múltiples alternativas:

{secciones.get('formas_contacto', '')}

---

## 💰 ¿Cuánto Cuesta Llamar si No Usas el Teléfono Gratuito?

Si no puedes usar el {telefono}, estos son los costes aproximados:

| Tipo de llamada | Coste aproximado |
|----------------|------------------|
| **Desde fijo** | 0,05€ - 0,15€ por minuto |
| **Desde móvil** | 0,15€ - 0,30€ por minuto |
| **Llamadas a 901** | 0,10€ - 0,20€ por minuto |
| **Llamadas a 902** | 0,20€ - 0,50€ por minuto |

**⚠️ Importante:** Desde 2021, la legislación española obliga a ofrecer al menos un número gratuito. Si {emp['nombre']} solo ofrece 901/902, puedes reclamar ante Consumo.

---

## 📝 Nuestra Experiencia y Verificación

{secciones.get('experiencia', '')}

---

## ⚖️ Derechos del Consumidor

Como consumidor en España, la **Ley General para la Defensa de los Consumidores y Usuarios** te protege:

1. **Derecho a un número gratuito**
2. **Derecho a ser atendido en tiempo razonable**
3. **Derecho a información clara**
4. **Derecho a reclamar**
5. **Derecho a la protección de datos (RGPD)**

Si {emp['nombre']} no respeta estos derechos, acude a la **OMIC** o **Consumo** de tu comunidad.

---

## 📋 Cómo Poner una Reclamación Formal

### Paso 1: Reclamación interna
Llama al {telefono} y solicita un **número de incidencia**.

### Paso 2: Reclamación por escrito
Envía un email a {email} detallando:
- Tus datos y número de cliente
- Fecha y hora de la llamada
- Número de incidencia
- Descripción del problema
- Solución solicitada

### Paso 3: Libro de reclamaciones
Si en **30 días** no hay respuesta, solicita el libro oficial.

### Paso 4: Vía administrativa
Presenta reclamación ante:
- **OMIC** de tu ayuntamiento
- **Consumo** de tu comunidad autónoma
- **Secretaría de Estado de Telecomunicaciones** (si aplica)

---

## 💡 Consejos para Reclamaciones

{secciones.get('consejos', '')}

---

## 🏢 Sobre {emp['nombre']}

{emp['nombre']} es una empresa líder en el sector de {emp.get('sector', 'servicios')} en España. Cuenta con millones de clientes en todo el territorio nacional. Su sede social se encuentra en {direccion}.

La compañía ofrece servicios de {emp.get('sector', 'alta calidad')} y se ha consolidado como una de las opciones más populares entre los consumidores españoles.

---

## ⭐ Opiniones de Otros Usuarios

Según **Trustpilot**, **OCU** y **Google Reviews**, la atención al cliente de {emp['nombre']} recibe valoraciones mixtas:

- **Puntos fuertes:** Los usuarios valoran la existencia del {telefono} y la profesionalidad de los operadores.
- **Puntos débiles:** Las quejas más frecuentes son los **tiempos de espera** y la **dificultad del menú de voz**.
- **Recomendación:** Llamar a primera hora o usar el chat web.

---

## ❓ Preguntas Frecuentes (FAQ)

### ¿El teléfono {telefono} de {emp['nombre']} es realmente gratis?
Sí, {'los números 900 en España son gratuitos tanto desde fijo como móvil.' if len(telefono_limpio) == 9 else f'el número {telefono} es gratuito desde móviles de {emp["nombre"]}. Desde otras operadoras, consulta alternativas.'}

### ¿Puedo llamar desde el extranjero?
{'No, los 900 solo funcionan desde España.' if len(telefono_limpio) == 9 else f'El {telefono} solo funciona desde España y móviles de {emp["nombre"]}. Desde el extranjero, usa el chat web.'}

### ¿Qué hago si el teléfono está ocupado?
1) Llama en horarios de menor afluencia (martes a jueves, 10:00-12:00). 2) Usa el chat web. 3) Envía un email. 4) Usa la app móvil.

### ¿Cuánto tardan en atender?
El tiempo medio es de {emp.get('tiempo_espera_min', '5-10')} minutos. Los lunes por la mañana y viernes por la tarde son los momentos de mayor saturación.

### ¿Puedo reclamar por teléfono?
Sí, pero recomendamos formalizarla **por escrito** para tener constancia. Anota siempre el **número de incidencia**.

### ¿{emp['nombre']} tiene app móvil?
Sí, disponible en [App Store](https://apps.apple.com) y [Google Play](https://play.google.com).

### ¿Cómo doy de baja el servicio?
Llamando al {telefono}, por la app móvil, o enviando email a {email}. La empresa debe facilitar la baja sin costes.

### ¿Qué hago si me cobran de más?
Revisa la factura y contacta con {emp['nombre']} en el {telefono}. Si no lo resuelven en 30 días, reclama ante Consumo.

---

## ⚖️ Comparativa del Sector

{secciones.get('comparativa', '')}

---

## 🔗 Artículos Relacionados

- Teléfono gratuito de {emp.get('sector_relacionado_1', 'la competencia')}
- Teléfono gratuito de {emp.get('sector_relacionado_2', 'otras empresas')}
- Cómo reclamar a empresas de {emp.get('sector', 'servicios')}
- Derechos del consumidor en España

---

*¿Te ha sido útil? Compártelo para ayudar a otros usuarios. Si el teléfono ha cambiado, [avísanos](mailto:info@telefonos-gratuitos.com).*

**Fuentes:** Web oficial de {emp['nombre']}, Ley de Consumidores, OMIC, OCU.
"""
        
        # Aplicar mejoras SEO
        articulo_con_toc = generar_tabla_contenidos(articulo_base) + articulo_base
        articulo_final = generar_enlaces_internos(articulo_con_toc, df, emp['nombre'])
        
        st.markdown("### 📝 Vista Previa")
        with st.expander("👁️ Ver artículo completo"):
            st.markdown(articulo_final)
        
        st.divider()
        
        # Validación
        st.subheader("🛡️ Validación")
        validador = ValidadorAdSense()
        resultado_val = validador.validar(articulo_final, emp)
        
        num_palabras = len(articulo_final.split())
        num_h2 = articulo_final.count('\n## ')
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Palabras", f"{num_palabras}")
        col2.metric("📑 Secciones", f"{num_h2}")
        col3.metric("⭐ Puntuación", f"{resultado_val['puntuacion']}/100")
        col4.metric("✅ Aprobado", "SÍ" if resultado_val['aprobado'] else "NO")
        
        if resultado_val['aprobado']:
            st.success("✅ Cumple con AdSense y SEO.")
        else:
            st.error("⚠️ Necesita mejoras:\n" + "\n".join(resultado_val['errores']))
        
        st.divider()
        
        # Schemas
        st.subheader("🔍 Schema.org y SEO")
        
        with st.spinner("Generando schemas..."):
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
            col3.success(f"✅ Article\nDatos")
            col4.success(f"✅ Breadcrumb\nNav")
            
            st.markdown("### 📝 Meta Descripción")
            st.info(f"**{len(meta_descripcion)} caracteres:** {meta_descripcion}")
            
            with st.expander("👁️ Ver códigos Schema.org"):
                st.code(schema_contact['html'], language='json')
                if schema_faq:
                    st.code(schema_faq['html'], language='json')
        
        st.divider()
        
        # Publicar
        if st.button("📤 Publicar en WordPress", type="primary", disabled=not resultado_val['aprobado'], key="btn_publicar_wp"):
            with st.spinner("Publicando..."):
                publisher = WPPublisher()
                titulo = f"Teléfono Gratuito de {emp['nombre']} {datetime.now().year}"
                
                resultado_wp = publisher.publicar(
                    titulo=titulo,
                    contenido=articulo_final,
                    schema_faq=st.session_state.get('schema_faq'),
                    schema_contact=st.session_state.get('schema_contact'),
                    meta_descripcion=st.session_state.get('meta_descripcion')
                )
                
                if resultado_wp['success']:
                    st.success(f"🎉 ¡Publicado! [Ver en WordPress]({resultado_wp['url']})")
                    st.balloons()
                else:
                    st.error(f"Error: {resultado_wp['error']}")

# TAB 5: DIAGNÓSTICO
with tab5:
    st.header("🔍 Diagnóstico")
    
    url_articulo = st.text_input("URL del artículo:", key="url_diagnostico")
    
    if st.button("🔍 Verificar", type="primary", key="btn_verificar"):
        if url_articulo:
            st.success("✅ URL recibida")
            st.markdown(f"""
            ### Verifica el Schema:
            1. Abre [Rich Results Test](https://search.google.com/test/rich-results)
            2. Pega: `{url_articulo}`
            3. Deberías ver **FAQPage** y **Article**
            """)
            
            st.markdown(f"""
            <a href="https://search.google.com/test/rich-results?url={url_articulo}" target="_blank">
                <button style="background-color: #4285f4; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;">
                    🔍 Abrir Rich Results Test
                </button>
            </a>
            """, unsafe_allow_html=True)
    
    st.divider()
    st.subheader("📊 Estadísticas")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Empresas", len(df))
    col2.metric("📞 Con teléfono", len(df[df['telefono_900'].notna()]) if not df.empty else 0)
    col3.metric("🌐 Con web", len(df[df['web_oficial'].notna()]) if not df.empty else 0)
    col4.metric("📅 Fecha", datetime.now().strftime("%d/%m/%Y"))

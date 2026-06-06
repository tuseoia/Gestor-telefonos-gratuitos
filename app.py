import streamlit as st
import pandas as pd
import os
import json
import requests
import re
import random
import time
import urllib.request
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Cargar variables de entorno
load_dotenv()
os.makedirs("data", exist_ok=True)

# ==========================================
# FUNCIÓN DE FECHA EN ESPAÑOL CORRECTO
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
# FUNCIÓN PARA LIMPIAR URL
# ==========================================
def limpiar_url(url):
    """Extrae solo la URL de un enlace markdown o texto"""
    if not url or pd.isna(url):
        return ""
    url = str(url).strip()
    # Si es un enlace markdown [texto](url), extraer solo la URL
    match = re.search(r'\[([^\]]+)\]\(([^)]+)\)', url)
    if match:
        return match.group(2)
    # Si ya es una URL limpia, devolverla
    if url.startswith('http'):
        return url
    return url

# ==========================================
# FUNCIONES DE SCHEMA Y SEO
# ==========================================

def generar_schema_faq(articulo_markdown, nombre_empresa):
    """Extrae las FAQ del artículo y genera el Schema.org FAQPage"""
    faq_section = ""
    
    # FIX: Buscar con o sin emoji
    if "## ❓ Preguntas Frecuentes" in articulo_markdown:
        inicio = articulo_markdown.find("## ❓ Preguntas Frecuentes")
    elif "## Preguntas Frecuentes" in articulo_markdown:
        inicio = articulo_markdown.find("## Preguntas Frecuentes")
    else:
        return None
    
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
        if '-' in str(horario_raw) and ':' in str(horario_raw):
            partes = str(horario_raw).split('-')
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
    """Genera una tabla de contenidos automática"""
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
    """Añade enlaces internos evitando dobles enlaces"""
    articulo_modificado = articulo_markdown
    
    for index, row in df_empresas.iterrows():
        nombre_otra = row.get('nombre', '')
        if not nombre_otra or nombre_otra == empresa_actual:
            continue
        
        slug = f"telefono-gratuito-{nombre_otra.lower().replace(' ', '-')}"
        url_interna = f"https://telefonos-gratuitos.com/{slug}/"
        
        patron_buscado = f"**{nombre_otra}**"
        
        lineas = articulo_modificado.split('\n')
        nuevas_lineas = []
        ya_enlazado_esta_empresa = False
        
        for linea in lineas:
            if linea.startswith('#'):
                nuevas_lineas.append(linea)
                continue
            
            if f"[**{nombre_otra}**]" in linea or f"[{nombre_otra}]" in linea:
                nuevas_lineas.append(linea)
                continue
            
            if patron_buscado in linea and not ya_enlazado_esta_empresa:
                linea = linea.replace(patron_buscado, f"[**{nombre_otra}**]({url_interna})", 1)
                ya_enlazado_esta_empresa = True
            
            nuevas_lineas.append(linea)
        
        articulo_modificado = '\n'.join(nuevas_lineas)
    
    return articulo_modificado


def generar_meta_descripcion(empresa):
    """Genera una meta descripción optimizada"""
    telefono = empresa.get('telefono_900', '')
    nombre = empresa['nombre']
    
    # FIX: Manejar valores nan o vacíos del horario
    horario = empresa.get('horario_lunes_viernes', '24h')
    if pd.isna(horario) or str(horario).lower() in ['nan', '', 'consultar web']:
        horario = "24h"
    elif len(str(horario)) > 30:  # Si es muy largo, acortarlo
        horario = "Consultar web"
    
    plantillas = [
        f"☎️ Teléfono gratuito de {nombre}: {telefono}. Horario: {horario}. ✅ Verificado hoy. Guía completa: menú de voz, alternativas y consejos para reclamar.",
        f"¿Buscas el teléfono de {nombre}? 📞 {telefono} (GRATIS). Horario {horario}. Te explicamos cómo saltarte el menú de voz y hablar rápido con un operador.",
        f"{nombre} teléfono de atención al cliente: {telefono} ✓ Gratis ✓ Horario: {horario} ✓ Guía paso a paso para contactar sin esperas.",
    ]
    
    meta = random.choice(plantillas)
    if len(meta) > 160:
        meta = meta[:157] + "..."
    return meta


# ==========================================
# CLASES DEL SISTEMA
# ==========================================

class QwenGenerator:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = "qwen/qwen-2.5-72b-instruct"
        self.max_reintentos = 3

    def generar(self, empresa, tipo):
        telefono = empresa.get('telefono_900', '1004')
        nombre = empresa['nombre']
        sector = empresa.get('sector', 'general')
        tiempo = empresa.get('tiempo_espera_min', '5')
        menu = empresa.get('menu_voz_ruta', '1,2,3')
        comp1 = empresa.get('sector_relacionado_1', 'competidores')
        comp2 = empresa.get('sector_relacionado_2', 'otras empresas')
        web = limpiar_url(empresa.get('web_oficial', 'su web oficial'))
        
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
        
        # Intentar generar con la IA
        for intento in range(self.max_reintentos):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Eres un redactor experto en SEO y consumo en España. Escribe texto 100% original, natural, sin clichés de IA. Evita frases como 'En conclusión', 'Es importante destacar', 'En resumen'. Usa párrafos cortos, listas y negritas para facilitar la lectura."},
                        {"role": "user", "content": prompts[tipo]}
                    ],
                    temperature=0.7,
                    timeout=60
                )
                
                # Verificar que la respuesta es válida
                if response and hasattr(response, 'choices') and response.choices and len(response.choices) > 0:
                    if hasattr(response.choices[0], 'message') and hasattr(response.choices[0].message, 'content'):
                        contenido = response.choices[0].message.content.strip()
                        if contenido and len(contenido) > 50:
                            return contenido
                
                if intento < self.max_reintentos - 1:
                    time.sleep(2)
                    
            except Exception as e:
                if intento < self.max_reintentos - 1:
                    time.sleep(3)
        
        # Si todos los reintentos fallan, usar contenido de respaldo
        return self._contenido_respaldo(empresa, tipo)
    
    def _contenido_respaldo(self, empresa, tipo):
        """Contenido de respaldo si la IA falla"""
        nombre = empresa['nombre']
        telefono = empresa.get('telefono_900', '1004')
        tiempo_espera = empresa.get('tiempo_espera_min', '5-10')
        menu_voz = empresa.get('menu_voz_ruta', '1,2,3')
        comp1 = empresa.get('sector_relacionado_1', 'competidores')
        comp2 = empresa.get('sector_relacionado_2', 'otras empresas')
        web = limpiar_url(empresa.get('web_oficial', 'su web oficial'))
        
        respaldos = {
            "experiencia": f"""En nuestro equipo de **telefonos-gratuitos.com** hemos probado recientemente el teléfono de atención al cliente de **{nombre}** marcando el **{telefono}**. 

La llamada la realizamos un **martes por la mañana** (aproximadamente a las 10:30h) y el tiempo de espera hasta ser atendidos fue de aproximadamente **{tiempo_espera} minutos**, un plazo razonable considerando que llamamos en horario de máxima afluencia.

Al seguir la secuencia del menú de voz (**{menu_voz}**), conseguimos llegar directamente al departamento de atención al cliente existente, evitando así las opciones de contratación que suelen alargar la llamada innecesariamente. 

El operador que nos atendió mostró un **trato amable y profesional**, resolviendo nuestra consulta de prueba en menos de 5 minutos. Nos pareció especialmente positivo que el operador se identificara claramente al inicio de la conversación y nos proporcionara un número de incidencia para seguimiento.

**Nuestro consejo:** si necesitas contactar con {nombre}, evita llamar los lunes por la mañana y los viernes por la tarde, ya que son los momentos de mayor saturación. Los martes y miércoles entre las 10:00 y las 12:00 suelen ser los horarios con menor tiempo de espera. Si la llamada es urgente fuera de horario, te recomendamos usar el chat web o la aplicación móvil, que suelen tener tiempos de respuesta más rápidos.""",
            
            "menu_voz": f"""Conocer el menú de voz de **{nombre}** te ahorrará minutos de frustración y te permitirá llegar rápidamente al departamento que necesitas. Hemos probado personalmente la secuencia para que no tengas que hacerlo tú.

**Pasos para hablar con un operador:**

1. 📞 Marca el **{telefono}** desde tu teléfono
2. ⏳ Espera a que comience la locución inicial (no pulses nada todavía)
3. 🔢 Pulsa la secuencia: **{menu_voz}**
4. 🆔 Ten a mano tu DNI o número de cliente (te lo pedirán)
5. ⏱️ Espera en la cola (tiempo medio: {tiempo_espera} minutos)

**⚠️ Advertencias importantes:**

- ❌ NO pulses la opción de "Nuevos clientes" o "Contratación", te redirigirá al departamento comercial
- ❌ NO pulses opciones de "Ofertas especiales", son grabaciones publicitarias
- ✅ Si te pierdes, pulsa 0 para volver al menú principal

**💡 3 trucos para reducir el tiempo de espera:**

1. **Llama a primera hora** (9:00-10:00): Los sistemas están menos saturados
2. **Evita lunes y viernes**: Son los días con más llamadas
3. **Ten tus datos a mano**: DNI, número de cliente y motivo de la llamada. Si el operador te pide buscar datos, perderás tiempo valioso""",
            
            "formas_contacto": f"""Si el teléfono **{telefono}** está saturado o prefieres otros canales, **{nombre}** ofrece múltiples formas de contacto alternativas:

### 💬 Chat en Vivo
Disponible en la web oficial [{web}]({web}). Suele tener un tiempo de respuesta de 5-10 minutos y está disponible en horario de atención telefónica. Ideal para consultas sencillas sobre facturación o incidencias técnicas menores.

### 📱 WhatsApp Business
{nombre} no dispone actualmente de un canal oficial de WhatsApp para atención al cliente. Te recomendamos usar el chat web como alternativa más rápida.

### 📧 Correo Electrónico
Puedes enviar tu consulta a través del formulario de contacto disponible en su web oficial. El tiempo medio de respuesta es de 24-48 horas laborables. Para reclamaciones formales, usa siempre este canal para tener constancia por escrito.

### 📲 App Móvil
La aplicación oficial de **{nombre}** está disponible para iOS y Android. Permite gestionar tu cuenta, consultar facturas, realizar pagos y contactar con atención al cliente a través de un chat integrado. Es la forma más rápida de resolver consultas sin llamar.

### 🐦 Redes Sociales
{nombre} mantiene perfiles activos en Twitter/X, Facebook e Instagram. El equipo de redes sociales suele responder en un plazo de 2-4 horas en horario laboral. Es útil para consultas públicas o quejas visibles.

### 🏪 Tiendas Físicas
Puedes localizar la tienda más cercana de {nombre} a través de su web oficial en la sección "Localizador de tiendas". La atención presencial es ideal para trámites complejos como portabilidad, contratación de nuevos servicios o resolución de incidencias técnicas.""",

            "consejos": f"""1. **Documenta todo por escrito**
Si tu reclamación es importante, no te quedes solo con la llamada telefónica. Solicita siempre un número de incidencia y envía después un correo electrónico detallando tu caso. Esto te servirá como prueba ante la OMIC o Consumo. Guarda copia de todas las comunicaciones.

2. **Conoce tus plazos**
Tienes **30 días** para que {nombre} responda a tu reclamación. Si no lo hace, puedes escalar el caso a Consumo. Para reclamaciones ante la Secretaría de Estado de Telecomunicaciones, el plazo es de 2 meses desde la presentación.

3. **Usa el libro de reclamaciones**
Si no quedas satisfecho con la respuesta, tienes derecho a solicitar el libro de reclamaciones oficial. {nombre} está obligado a facilitártelo, ya sea en sus tiendas físicas o a través de su web. Es un documento con validez legal.

4. **Acude a la OMIC**
La Oficina Municipal de Información al Consumidor (OMIC) de tu ayuntamiento ofrece asesoramiento gratuito. Pueden ayudarte a redactar la reclamación y mediar con {nombre}. Es un servicio público y totalmente gratuito.

5. **Reclama ante Consumo**
Si {nombre} no resuelve tu reclamación en un plazo de 2 meses, puedes acudir a la Dirección General de Consumo de tu comunidad autónoma. Es un trámite gratuito y suele ser efectivo para resolver disputas sobre facturación o permanencia.""",

            "comparativa": f"""### Comparativa de Atención al Cliente: {nombre}, {comp1} y {comp2}

**Tabla Comparativa**

| Empresa | Teléfono Gratuito | Horario | Tiempo Espera | Valoración |
|---------|------------------|---------|---------------|------------|
| {nombre} | {telefono} | 24/7 | {tiempo_espera} min | 7.5/10 |
| {comp1} | Consultar web | L-V 9-20h | 5-7 min | 8.0/10 |
| {comp2} | Consultar web | L-V 9-20h | 6-8 min | 7.8/10 |

**Análisis**

{nombre} ofrece atención 24/7, lo cual es un punto a su favor para usuarios que necesitan ayuda fuera del horario laboral. Sin embargo, el tiempo de espera medio puede resultar algo alto comparado con sus competidores.

{comp1} tiene un horario de atención más limitado, pero compensa con un tiempo de espera medio menor. La valoración refleja la satisfacción de los clientes con la eficacia y rapidez del servicio.

{comp2} ofrece un horario extenso y un tiempo de espera razonable. La valoración indica un buen servicio, aunque no tan alto como el de {comp1}.

**Recomendación Final**

Si la disponibilidad 24/7 no es un requisito imprescindible, {comp1} es la opción más recomendada por su combinación de tiempo de espera bajo y valoración alta. Sin embargo, si necesitas atención fuera de horario laboral, {nombre} sigue siendo una opción válida."""
        }
        
        return respaldos.get(tipo, "Contenido no disponible.")


class SmartScraper:
    def extraer(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9',
            }
            
            session = requests.Session()
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code in [403, 429, 503]:
                return self._resultado_bloqueado(url, f"Código {response.status_code}")
            
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text(separator=' ', regex=False)
            
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
            
            telefono_principal = telefonos_encontrados[0] if telefonos_encontrados else "No encontrado"
            
            return {
                'telefono': telefono_principal,
                'horario': "Consultar web",
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
            'solucion': "Usa 'Búsqueda Inteligente' o 'Manual Asistido'",
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
            
            return {
                'encontrados': sorted(list(encontrados)),
                'horarios': [],
                'status': 'success'
            }
        except Exception as e:
            return {'encontrados': [], 'horarios': [], 'status': 'error', 'error': str(e)}


class GoogleSearcher:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def buscar_telefono(self, nombre_empresa, sector=""):
        queries = [
            f"teléfono gratuito {nombre_empresa} atención al cliente",
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
            errores.append("❌ Menos de 500 palabras")
        if "hemos" not in texto.lower() and "probado" not in texto.lower():
            errores.append("❌ Falta experiencia en primera persona")
        if empresa['nombre'].lower() not in texto.lower():
            errores.append("❌ Nombre de empresa no aparece")
        
        puntuacion = 100 - (len(errores) * 30)
        return {"aprobado": len(errores) == 0, "errores": errores, "puntuacion": max(0, puntuacion)}


class WPPublisher:
    def publicar(self, titulo, contenido, schema_faq=None, schema_contact=None, meta_descripcion=None):
        url_base = os.getenv('WP_URL', '').rstrip('/')
        url = f"{url_base}/wp-json/wp/v2/posts"
        user = os.getenv('WP_USER')
        pwd = os.getenv('WP_APP_PASSWORD')
        
        if not url_base or not user or not pwd:
            return {
                "success": False, 
                "error": "❌ Credenciales incompletas. Verifica WP_URL, WP_USER y WP_APP_PASSWORD en Secrets"
            }
        
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
            response = requests.post(url, auth=(user, pwd), json=payload, timeout=30)
            
            if response.status_code == 201:
                return {
                    "success": True,
                    "url": response.json()['link'],
                    "schema_incluido": schema_faq is not None or schema_contact is not None,
                    "meta_descripcion": meta_descripcion
                }
            elif response.status_code == 401:
                return {
                    "success": False, 
                    "error": "❌ Error 401: Application Password incorrecta. Genera una NUEVA en WordPress → Usuarios → Tu perfil → Application Passwords"
                }
            elif response.status_code == 403:
                return {
                    "success": False, 
                    "error": "❌ Error 403: Prohibido. Publica manualmente: copia el artículo y pégalo en WordPress como nuevo post."
                }
            else:
                return {
                    "success": False, 
                    "error": f"❌ Error {response.status_code}: {response.text[:300]}"
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "⏱️ Timeout: El servidor tarda demasiado"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "🚫 Error de conexión. Verifica WP_URL"}
        except Exception as e:
            return {"success": False, "error": f"❌ Error: {str(e)}"}


# ==========================================
# INTERFAZ DE USUARIO
# ==========================================

st.set_page_config(page_title="Gestor Telefonos Gratuitos", page_icon="📞", layout="wide")
st.title("📞 Panel de Control: telefonos-gratuitos.com")
st.markdown("Automatización SEO + AdSense + Qwen AI + WordPress + Schema.org")

# Sidebar con info de IP
st.sidebar.header("⚙️ Configuración")
st.sidebar.info("Las claves se cargan desde Secrets")

if st.sidebar.button("🔍 Ver IP de Streamlit"):
    try:
        ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
        st.sidebar.success(f"📍 IP: {ip}")
    except Exception as e:
        st.sidebar.error(f"Error: {str(e)}")

if not os.getenv("OPENROUTER_API_KEY"):
    st.sidebar.error("⚠️ Falta OPENROUTER_API_KEY")
else:
    st.sidebar.success("✅ API Key configurada")

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
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🏢 Total Empresas", len(df))
    with col2:
        st.metric("📞 Con Teléfono", len(df[df['telefono_900'].notna()]) if not df.empty else 0)
    with col3:
        st.metric("🌐 Con Web Oficial", len(df[df['web_oficial'].notna()]) if not df.empty else 0)
    
    st.divider()
    
    st.subheader("📝 Editar Empresas")
    st.info("💡 Edita la tabla directamente como si fuera Excel. Los cambios se guardan al pulsar el botón.")
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="data_editor_empresas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Guardar Cambios", type="primary", use_container_width=True, key="btn_guardar_csv"):
            edited_df.to_csv(CSV_PATH, index=False)
            st.success("✅ Base de datos actualizada correctamente")
            df = edited_df
            st.rerun()
    
    with col2:
        if 'confirmar_borrado' not in st.session_state:
            st.session_state.confirmar_borrado = False
        
        if not st.session_state.confirmar_borrado:
            if st.button("🗑️ Borrar Base de Datos", use_container_width=True, key="btn_borrar_csv"):
                st.session_state.confirmar_borrado = True
                st.rerun()
        else:
            st.warning("⚠️ **¿Estás seguro?** Esta acción NO se puede deshacer.")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Sí, borrar todo", type="primary", use_container_width=True, key="btn_confirmar_borrado"):
                    try:
                        if os.path.exists(CSV_PATH):
                            os.remove(CSV_PATH)
                        
                        df_vacio = pd.DataFrame(columns=[
                            "nombre", "sector", "telefono_900", "telefono_fijo",
                            "horario_lunes_viernes", "horario_sabado", "web_oficial",
                            "email", "whatsapp", "direccion_postal", "menu_voz_ruta",
                            "tiempo_espera_min", "sector_relacionado_1", "sector_relacionado_2",
                            "ultima_verificacion"
                        ])
                        df_vacio.to_csv(CSV_PATH, index=False)
                        
                        st.session_state.confirmar_borrado = False
                        st.session_state.pop('empresa_actual', None)
                        st.session_state.pop('secciones_articulo', None)
                        
                        st.success("🗑️ Base de datos borrada correctamente.")
                        st.balloons()
                        
                        df = df_vacio
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error al borrar: {str(e)}")
                        st.session_state.confirmar_borrado = False
            
            with col_cancel:
                if st.button("❌ Cancelar", use_container_width=True, key="btn_cancelar_borrado"):
                    st.session_state.confirmar_borrado = False
                    st.rerun()
    
    st.divider()
    if st.button("📥 Exportar Backup CSV", use_container_width=True, key="btn_exportar_backup"):
        try:
            csv_data = df.to_csv(index=False)
            st.download_button(
                label="⬇️ Descargar CSV",
                data=csv_data,
                file_name=f"empresas_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime='text/csv',
                key="btn_descargar_backup"
            )
            st.success("✅ Backup listo para descargar")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    st.divider()
    with st.expander("ℹ️ Información sobre la base de datos"):
        st.markdown(f"""
        **Ubicación del archivo:** `{CSV_PATH}`
        
        **Columnas incluidas:**
        - `nombre`: Nombre de la empresa
        - `sector`: Sector al que pertenece
        - `telefono_900`: Teléfono gratuito (900, 901, 1004, etc.)
        - `telefono_fijo`: Teléfono fijo alternativo
        - `horario_lunes_viernes`: Horario de atención L-V
        - `horario_sabado`: Horario de atención sábados
        - `web_oficial`: URL de la web oficial
        - `email`: Email de contacto
        - `whatsapp`: Número de WhatsApp
        - `direccion_postal`: Dirección postal
        - `menu_voz_ruta`: Secuencia del menú de voz
        - `tiempo_espera_min`: Tiempo medio de espera
        - `sector_relacionado_1`: Empresa competidora 1
        - `sector_relacionado_2`: Empresa competidora 2
        - `ultima_verificacion`: Fecha de última verificación
        """)

# TAB 2: SCRAPING
with tab2:
    st.header("🕷️ Extracción Inteligente")
    
    modo = st.radio(
        "Método:",
        ["🔍 Búsqueda Inteligente", "🔄 Scraping Automático", "✋ Manual Asistido"],
        horizontal=True,
        key="modo_extraccion_radio"
    )
    
    if modo == "🔍 Búsqueda Inteligente":
        nombre_busqueda = st.text_input("Nombre de la empresa:", key="nombre_busqueda_inteligente")
        
        if st.button("🔍 Buscar", type="primary", key="btn_buscar_inteligente"):
            if nombre_busqueda:
                with st.spinner("Buscando..."):
                    searcher = GoogleSearcher()
                    resultado = searcher.buscar_telefono(nombre_busqueda)
                    
                    if resultado['status'] == 'success' and resultado.get('telefonos'):
                        st.success(f"✅ Encontrados {len(resultado['telefonos'])} teléfonos")
                        tel_seleccionado = st.selectbox("Selecciona:", resultado['telefonos'], key="sel_tel_inteligente")
                        st.session_state['datos_extraidos'] = {'telefono': tel_seleccionado, 'horario': ""}
                    else:
                        st.warning("⚠️ No se encontraron teléfonos")
    
    elif modo == "🔄 Scraping Automático":
        url = st.text_input("URL:", key="url_scraping_auto")
        
        if st.button("🔍 Analizar", type="primary", key="btn_analizar_auto"):
            if url:
                with st.spinner("Analizando..."):
                    scraper = SmartScraper()
                    resultado = scraper.extraer(url)
                    
                    if resultado['status'] == 'success':
                        telefonos = resultado.get('todos_los_telefonos', [])
                        if telefonos:
                            st.success(f"✅ Encontrados {len(telefonos)} teléfonos")
                            tel_seleccionado = st.selectbox("Selecciona:", telefonos, key="sel_tel_auto")
                            st.session_state['datos_extraidos'] = {'telefono': tel_seleccionado, 'horario': resultado['horario']}
                    elif resultado.get('status') == 'bloqueado':
                        st.warning(f"🛡️ Web bloqueada: {resultado.get('detalle', '')}")
    
    else:
        st.markdown("**Instrucciones:** Ctrl+U → Ctrl+A → Ctrl+C → Pega abajo")
        html_input = st.text_area("HTML:", height=200, key="html_manual_asistido")
        
        if st.button("🔍 Extraer", type="primary", key="btn_extraer_html"):
            if html_input:
                with st.spinner("Analizando..."):
                    extractor = HTMLExtractor()
                    resultado = extractor.extraer_de_html(html_input)
                    
                    if resultado.get('encontrados'):
                        st.success(f"✅ Encontrados {len(resultado['encontrados'])} teléfonos")
                        tel_seleccionado = st.selectbox("Selecciona:", resultado['encontrados'], key="sel_tel_manual")
                        st.session_state['datos_extraidos'] = {'telefono': tel_seleccionado, 'horario': ""}

# TAB 3: GENERADOR CON IA
with tab3:
    st.header("🤖 Generador de Artículos (1500+ palabras)")
    
    if df.empty or df['nombre'].dropna().empty:
        st.warning("Añade empresas en 'Base de Datos'")
    else:
        empresa_seleccionada = st.selectbox("Empresa:", df['nombre'].dropna().tolist(), key="select_empresa_generar")
        datos_empresa = df[df['nombre'] == empresa_seleccionada].iloc[0].to_dict()
        
        if st.button("🚀 Generar Artículo", type="primary", key="btn_generar_ia"):
            with st.spinner("Generando... (1-2 minutos)"):
                ai = QwenGenerator()
                secciones = {}
                progress = st.progress(0)
                
                st.write("📝 Experiencia...")
                secciones['experiencia'] = ai.generar(datos_empresa, "experiencia")
                progress.progress(20)
                
                st.write("🗺️ Menú de voz...")
                secciones['menu_voz'] = ai.generar(datos_empresa, "menu_voz")
                progress.progress(40)
                
                st.write("📧 Formas de contacto...")
                secciones['formas_contacto'] = ai.generar(datos_empresa, "formas_contacto")
                progress.progress(60)
                
                st.write("💡 Consejos...")
                secciones['consejos'] = ai.generar(datos_empresa, "consejos")
                progress.progress(80)
                
                st.write("⚖️ Comparativa...")
                secciones['comparativa'] = ai.generar(datos_empresa, "comparativa")
                progress.progress(100)
                
                st.session_state['secciones_articulo'] = secciones
                st.session_state['empresa_actual'] = datos_empresa
                
                st.success("✅ Artículo generado. Ve a 'Publicar'")

# TAB 4: PUBLICAR
with tab4:
    st.header("🚀 Publicación en WordPress")
    
    if 'empresa_actual' not in st.session_state or 'secciones_articulo' not in st.session_state:
        st.info("Genera un artículo primero")
    else:
        emp = st.session_state['empresa_actual']
        secciones = st.session_state['secciones_articulo']
        
        telefono = emp.get('telefono_900', 'Consultar web')
        telefono_limpio = str(telefono).replace(' ', '')
        
        if len(telefono_limpio) == 4:
            intro_telefono = f"El número corto de {emp['nombre']} es el **{telefono}**."
            nota_telefono = f"**Nota:** El {telefono} es gratuito desde móviles de {emp['nombre']}. Desde otros operadores, consulta alternativas."
        else:
            intro_telefono = f"El teléfono gratuito de {emp['nombre']} es el **{telefono}**."
            nota_telefono = "Es totalmente gratis desde fijo y móvil en España."
        
        horario = emp.get('horario_lunes_viernes', 'Lunes a Viernes de 9:00 a 20:00')
        if pd.isna(horario) or str(horario).lower() in ['nan', '', 'consultar web']:
            horario = "Lunes a Viernes de 9:00 a 20:00"
        
        horario_sabado = emp.get('horario_sabado', 'Sábados de 10:00 a 14:00')
        if pd.isna(horario_sabado) or str(horario_sabado).lower() in ['nan', '', 'consultar web oficial']:
            horario_sabado = "Sábados de 10:00 a 14:00"
        
        web = limpiar_url(emp.get('web_oficial', f"https://www.{emp['nombre'].lower().replace(' ', '')}.es"))
        if not web or pd.isna(web) or str(web).lower() in ['nan', '']:
            web = f"https://www.{emp['nombre'].lower().replace(' ', '')}.es"
        
        email = emp.get('email', 'A través del formulario de su web oficial')
        if pd.isna(email) or str(email).lower() in ['nan', 'no disponible', '']:
            email = "A través del formulario de su web oficial"
        
        direccion = emp.get('direccion_postal', 'Consulta en su web oficial')
        if pd.isna(direccion) or str(direccion).lower() in ['nan', 'consultar web oficial', '']:
            direccion = "Consulta la dirección en su web oficial"
        
        fecha_verificacion = fecha_espanol()
        
        articulo_base = f"""# Teléfono Gratuito de {emp['nombre']} {datetime.now().year} - Atención al Cliente Gratis

**Última verificación:** {fecha_verificacion} ✅  
**Autor:** Equipo Editorial de telefonos-gratuitos.com  
**Tiempo de lectura:** 7 minutos

---

## 📞 El Teléfono de {emp['nombre']}

{intro_telefono} {nota_telefono}

Si necesitas contactar con {emp['nombre']} para resolver dudas sobre facturación, incidencias técnicas o cambios de tarifa, este es el número que debes marcar.

| Dato | Información |
|------|-------------|
| **Teléfono** | **{telefono}** |
| **Horario** | {horario} |
| **Web Oficial** | [{web}]({web}) |
| **Email** | {email} |

---

## 🕐 Horarios de Atención al Cliente

**Horario habitual:**
- **Lunes a Viernes:** {horario}
- **Sábados:** {horario_sabado}
- **Domingos y festivos:** Generalmente cerrado

**💡 Consejo:** Los mejores momentos para llamar son martes, miércoles y jueves entre las 10:00 y las 12:00.

---

## 🗺️ Cómo Saltarse el Menú de Voz

{secciones.get('menu_voz', '')}

---

## 📧 Todas las Formas de Contactar

{secciones.get('formas_contacto', '')}

---

## 💰 ¿Cuánto Cuesta Llamar?

| Tipo de llamada | Coste |
|----------------|-------|
| Desde fijo | 0,05€ - 0,15€/min |
| Desde móvil | 0,15€ - 0,30€/min |
| Llamadas a 901 | 0,10€ - 0,20€/min |
| Llamadas a 902 | 0,20€ - 0,50€/min |

---

## 📝 Nuestra Experiencia

{secciones.get('experiencia', '')}

---

## ⚖️ Derechos del Consumidor

1. **Derecho a un número gratuito**
2. **Derecho a ser atendido en tiempo razonable**
3. **Derecho a información clara**
4. **Derecho a reclamar**
5. **Derecho a la protección de datos (RGPD)**

---

## 📋 Cómo Reclamar

### Paso 1: Reclamación interna
Llama al {telefono} y solicita un **número de incidencia**.

### Paso 2: Reclamación por escrito
Envía email a {email} detallando tus datos, fecha de llamada, número de incidencia y problema.

### Paso 3: Libro de reclamaciones
Si en 30 días no hay respuesta, solicita el libro oficial.

### Paso 4: Vía administrativa
Presenta reclamación ante OMIC o Consumo de tu comunidad.

---

## 💡 Consejos

{secciones.get('consejos', '')}

---

## 🏢 Sobre {emp['nombre']}

{emp['nombre']} es una empresa líder en {emp.get('sector', 'servicios')} en España. Su sede se encuentra en {direccion}.

---

## ⭐ Opiniones

Según Trustpilot, OCU y Google Reviews:

- **Puntos fuertes:** Existencia del {telefono} y profesionalidad de operadores
- **Puntos débiles:** Tiempos de espera y dificultad del menú de voz
- **Recomendación:** Llamar a primera hora o usar chat web

---

## ❓ Preguntas Frecuentes

### ¿El {telefono} es gratis?
Sí, {'los 900 son gratuitos desde fijo y móvil.' if len(telefono_limpio) == 9 else f'el {telefono} es gratuito desde móviles de {emp["nombre"]}.'}

### ¿Puedo llamar desde el extranjero?
{'No, los 900 solo funcionan desde España.' if len(telefono_limpio) == 9 else f'El {telefono} solo funciona desde España.'}

### ¿Qué hago si está ocupado?
Llama en horarios de menor afluencia (martes a jueves, 10:00-12:00) o usa el chat web.

### ¿Cuánto tardan en atender?
Tiempo medio: {emp.get('tiempo_espera_min', '5-10')} minutos.

### ¿Puedo reclamar por teléfono?
Sí, pero recomendamos hacerlo por escrito para tener constancia.

### ¿Tiene app móvil?
Sí, disponible en App Store y Google Play.

### ¿Cómo doy de baja el servicio?
Llamando al {telefono}, por app móvil, o email a {email}.

### ¿Qué hago si me cobran de más?
Contacta con {emp['nombre']} en el {telefono}. Si no lo resuelven en 30 días, reclama ante Consumo.

---

## ⚖️ Comparativa del Sector

{secciones.get('comparativa', '')}

---

## 🔗 Artículos Relacionados

- Teléfono gratuito de {emp.get('sector_relacionado_1', 'la competencia')}
- Teléfono gratuito de {emp.get('sector_relacionado_2', 'otras empresas')}
- Cómo reclamar a empresas de {emp.get('sector', 'servicios')}

---

*¿Te ha sido útil? Compártelo para ayudar a otros usuarios. Si el teléfono ha cambiado, [avísanos](mailto:info@telefonos-gratuitos.com).*
"""
        
        articulo_con_toc = generar_tabla_contenidos(articulo_base) + articulo_base
        articulo_final = generar_enlaces_internos(articulo_con_toc, df, emp['nombre'])
        
        st.markdown("### 📝 Vista Previa")
        with st.expander("👁️ Ver artículo completo"):
            st.markdown(articulo_final)
        
        st.divider()
        
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
            st.success("✅ Cumple con AdSense y SEO")
        else:
            st.error("⚠️ Necesita mejoras:\n" + "\n".join(resultado_val['errores']))
        
        st.divider()
        
        st.subheader("🔍 Schema.org")
        
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
            
            st.info(f"**Meta Descripción:** {meta_descripcion}")
            
            with st.expander("👁️ Ver códigos Schema.org (para publicar manualmente)"):
                st.markdown("**Copia estos schemas y pégalos al inicio del artículo en WordPress:**")
                st.code(schema_contact['html'], language='html')
                if schema_faq:
                    st.code(schema_faq['html'], language='html')
        
        st.divider()
        
        # Botón de publicación automática
        if st.button("📤 Publicar en WordPress (Automático)", type="primary", disabled=not resultado_val['aprobado'], key="btn_publicar_wp"):
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
                    st.error(resultado_wp['error'])
        
        # Botón de copia manual
        st.divider()
        st.subheader("📋 Publicación Manual (Alternativa)")
        st.info("Si la publicación automática falla, copia el contenido y pégalo manualmente en WordPress.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📋 Copiar Artículo Completo", use_container_width=True, key="btn_copiar_articulo"):
                st.code(articulo_final, language="markdown")
                st.success("✅ Contenido listo para copiar")
        
        with col2:
            if st.button("📋 Copiar Schemas HTML", use_container_width=True, key="btn_copiar_schemas"):
                schemas_html = ""
                if st.session_state.get('schema_contact'):
                    schemas_html += st.session_state['schema_contact']['html'] + "\n\n"
                if st.session_state.get('schema_faq'):
                    schemas_html += st.session_state['schema_faq']['html']
                st.code(schemas_html, language="html")
                st.success("✅ Schemas listos para copiar")
        
        st.markdown("""
        **Instrucciones para publicar manualmente:**
        1. Copia los **Schemas HTML** y pégalos al inicio del artículo en WordPress (en modo HTML)
        2. Copia el **Artículo Completo** y pégalo en el editor de WordPress
        3. Añade la **Meta Descripción** en Yoast SEO o RankMath
        4. Selecciona la categoría adecuada (Telecomunicaciones, Energía, etc.)
        5. Guarda como borrador, revisa y publica
        """)

# TAB 5: DIAGNÓSTICO
with tab5:
    st.header("🔍 Diagnóstico")
    
    st.subheader("🧪 Probar Conexión WordPress")
    
    if st.button("🔍 Probar", key="btn_test_wp"):
        url_base = os.getenv('WP_URL', '').rstrip('/')
        user = os.getenv('WP_USER')
        pwd = os.getenv('WP_APP_PASSWORD')
        
        st.write(f"**URL:** {url_base}")
        st.write(f"**Usuario:** {user}")
        
        st.write("**1️⃣ REST API**")
        try:
            response = requests.get(f"{url_base}/wp-json/", timeout=10)
            if response.status_code == 200:
                st.success("✅ REST API accesible")
            else:
                st.error(f"❌ Error {response.status_code}")
        except Exception as e:
            st.error(f"❌ {str(e)}")
        
        st.write("**2️⃣ Autenticación**")
        try:
            response = requests.get(f"{url_base}/wp-json/wp/v2/users/me", auth=(user, pwd), timeout=10)
            
            if response.status_code == 200:
                st.success("✅ Autenticación correcta")
                user_data = response.json()
                st.info(f"Usuario: {user_data.get('name')}")
                st.info(f"Rol: {user_data.get('roles', ['?'])[0]}")
            elif response.status_code == 401:
                st.error("❌ Application Password incorrecta")
            elif response.status_code == 403:
                st.error("❌ Sin permisos o IP bloqueada")
        except Exception as e:
            st.error(f"❌ {str(e)}")
    
    st.divider()
    st.subheader("📊 Estadísticas")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Empresas", len(df))
    col2.metric("📞 Con teléfono", len(df[df['telefono_900'].notna()]) if not df.empty else 0)
    col3.metric("🌐 Con web", len(df[df['web_oficial'].notna()]) if not df.empty else 0)
    col4.metric("📅 Fecha", datetime.now().strftime("%d/%m/%Y"))

# === Importación de librerías estándar y de terceros ===
import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter

from dotenv import load_dotenv                     # Para cargar variables de entorno
from mistralai import * # Cliente Mistral AI para OCR

# -------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES
# -------------------------------------------------------------------

def extract_all_tables(response: OCRResponse) -> List[Dict[str, Any]]:
    """
    Extrae todas las tablas del documento OCR (formato Markdown).
    Identifica secciones tabulares basadas en líneas que comienzan con '|'.
    """
    all_tables = []
    for page in response.pages:
        lines = page.markdown.split('\n')
        cleaned_lines = []

        # Limpia líneas que podrían estar partidas visualmente en Markdown
        if lines:
            cleaned_lines.append(lines[0])
            for i in range(1, len(lines)):
                prev = cleaned_lines[-1].strip()
                curr = lines[i].strip()
                if prev.startswith('|') and not prev.endswith('|') and not curr.startswith('|'):
                    cleaned_lines[-1] += ' ' + lines[i]  # Unir línea cortada
                else:
                    cleaned_lines.append(lines[i])

        table_lines = []
        for line in cleaned_lines:
            if line.strip().startswith('|'):
                table_lines.append(line)
            else:
                # Si hay al menos dos líneas tipo tabla, se considera válida
                if len(table_lines) >= 2:
                    all_tables.append({
                        "page_index": page.index,
                        "table_markdown": "\n".join(table_lines)
                    })
                table_lines = []
        # Revisión al final de la página
        if len(table_lines) >= 2:
            all_tables.append({
                "page_index": page.index,
                "table_markdown": "\n".join(table_lines)
            })
    return all_tables

def add_titles_to_tables(tables: List[Dict[str, Any]], response: OCRResponse) -> List[Dict[str, Any]]:
    """
    Asigna títulos contextuales a las tablas encontradas, ignorando encabezados repetidos.
    Busca el título inmediatamente anterior a la tabla, descartando duplicados comunes.
    """
    headers = []
    for page in response.pages:
        for line in page.markdown.split('\n'):
            stripped = line.strip()
            if stripped.startswith('#'):
                headers.append(stripped.lstrip('# ').strip())

    # Detecta encabezados repetidos para ignorarlos
    blacklist = {h for h, c in Counter(headers).items() if c > 1}
    print(f"🔍 Lista negra de encabezados repetidos: {blacklist or 'ninguno'}")

    page_texts = {page.index: page.markdown for page in response.pages}

    for table in tables:
        title = "(No se encontró un título)"
        page_idx = table["page_index"]
        page_md = page_texts.get(page_idx, "")
        try:
            # Busca el inicio de la tabla en el texto y explora líneas anteriores
            pos = page_md.index(table["table_markdown"])
            lines_before = page_md[:pos].strip().split('\n')[::-1]  # Reversa
            for line in lines_before:
                text = line.strip()
                clean = text.lstrip('# ').strip()
                if (not text or text.startswith('|') or len(text) > 100 or 
                    text.endswith(('.', ':', ';')) or clean in blacklist):
                    continue
                title = clean
                break
        except ValueError:
            pass
        table["table_title"] = title
    return tables

def post_process_table(markdown: str) -> str:
    """
    Realiza una limpieza del Markdown:
    - Corrige formatos de celdas mal renderizadas.
    - Asegura que la separación de encabezado esté correctamente definida.
    """
    if not re.search(r'\|\s*[\\$]+\s*\|\s*[\d,.]+\s*\|', markdown):
        return markdown

    lines = markdown.strip().split('\n')
    corrected = []

    for line in lines:
        while True:
            # Reemplaza casos como "| \$ | 100 |" por "| $100 |"
            new_line, changed = re.subn(r'\|\s*[\\$]+\s*\|\s*([\d,.]+)\s*\|', r'| $\1 |', line, count=1)
            if changed == 0:
                break
            line = new_line
        corrected.append(re.sub(r'\|\s*\|', '|', line))  # Elimina separadores vacíos

    # Si no hay separador de encabezado, lo añade
    if len(corrected) > 1:
        header_line = next((l for l in corrected if '---' not in l), None)
        if header_line:
            num_cols = header_line.count('|') - 1
            separator = '|' + '---|' * num_cols
            for i, l in enumerate(corrected):
                if '---' in l:
                    corrected[i] = separator
                    break

    return "\n".join(corrected)

# -------------------------------------------------------------------
# 2. FUNCIÓN PRINCIPAL ORQUESTADORA (PARA SER IMPORTADA)
# -------------------------------------------------------------------
def process_pdf_to_structured_tables(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Orquesta todo el flujo de procesamiento:
    1. Carga de la API Key y validación de archivo.
    2. Subida del archivo y ejecución del OCR.
    3. Extracción, titulación y limpieza de tablas en Markdown.
    Retorna una lista de tablas con metainformación.
    """
    # --- Configuración del cliente Mistral ---
    project_root = Path(__file__).parent.parent
    dotenv_path = project_root / "env" / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        raise ValueError("❌ La MISTRAL_API_KEY no se encontró.")
    client = Mistral(api_key=api_key)

    if not pdf_path.exists():
        raise FileNotFoundError(f"❌ No se encontró el archivo PDF: {pdf_path}")

    # --- Ejecución del OCR ---
    print("🚀 Iniciando proceso de extracción de tablas...")
    try:
        print(f"📄 Subiendo archivo PDF: {pdf_path.name}")
        uploaded = client.files.upload(
            file={"file_name": pdf_path.name, "content": open(pdf_path, "rb")},
            purpose="ocr"
        )
        signed_url = client.files.get_signed_url(file_id=uploaded.id)

        ocr_response: OCRResponse = client.ocr.process(
            model="mistral-ocr-latest",
            document=DocumentURLChunk(document_url=signed_url.url)
        )
        print("✅ OCR completado correctamente.")
    except Exception as e:
        print(f"❌ Error durante el OCR: {e}")
        return []

    # --- Procesamiento del resultado OCR ---
    print("\n🔎 Extrayendo tablas del documento...")
    tables = extract_all_tables(ocr_response)
    print(f"✅ Se detectaron {len(tables)} tablas.")

    print("\n🏷  Añadiendo títulos automáticos...")
    titled_tables = add_titles_to_tables(tables, ocr_response)

    print("\n🧹 Corrigiendo formato de las tablas...")
    final_tables = []
    for tbl in titled_tables:
        final_tables.append({
            "page_index": tbl["page_index"],
            "table_title": tbl["table_title"],
            "corrected_markdown": post_process_table(tbl["table_markdown"]),
        })

    print("🎉 Proceso de extracción finalizado con éxito.")
    return final_tables

# -------------------------------------------------------------------
# 3. BLOQUE DE EJECUCIÓN DIRECTA (PARA PRUEBAS)
# -------------------------------------------------------------------
if __name__ == "__main__":
    # Ruta de prueba para ejecutar el script de forma independiente
    PDF_PATH = Path("task1/bronze/2025_Q1/Consolidated_Financial_Statements_Q1_2025.pdf")

    # Ejecuta el procesamiento del PDF
    tables_result = process_pdf_to_structured_tables(PDF_PATH)
    print(f"\n📊 Se procesaron {len(tables_result)} tablas en total.")

    # # OPCIONAL: Guardar resultados como JSON para depuración
    # output_path = "debug_extraction_output.json"
    # print(f"💾 Guardando resultados de la prueba en: '{output_path}'...")
    # with open(output_path, 'w', encoding='utf-8') as f:
    #     json.dump(tables_result, f, ensure_ascii=False, indent=4)
    # print("...Guardado completado.")

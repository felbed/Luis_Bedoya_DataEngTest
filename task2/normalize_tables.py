import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

# ¡AQUÍ ESTÁ LA MAGIA! Importamos la función principal del otro script.
# Asegúrate de que 'extract_from_pdfs.py' esté en el mismo directorio.
from extract_from_pdfs import process_pdf_to_structured_tables

# --------------------------------------------------------------------------
# --- 1. CONFIGURACIÓN INICIAL ---
# --------------------------------------------------------------------------
# Definimos la ruta del PDF que queremos procesar
PDF_INPUT_PATH = Path("task1/bronze/2025_Q1/Consolidated_Financial_Statements_Q1_2025.pdf")
PARQUET_OUTPUT_PATH = Path("task2/silver/q1_2025_tables.parquet")

# --------------------------------------------------------------------------
# --- 2. FUNCIONES DE NORMALIZACIÓN ---
# --------------------------------------------------------------------------

def clean_numeric_value(value_str: str) -> Optional[float]:
    """
    Convierte una cadena de texto de una tabla financiera a un número flotante.
    Maneja '$', comas, paréntesis para negativos y guiones.
    """
    if not isinstance(value_str, str) or not value_str.strip():
        return None
    
    cleaned_str = value_str.strip().replace('$', '').replace(',', '')
    
    if cleaned_str in ('—', '-'):
        return None
    
    is_negative = False
    if cleaned_str.startswith('(') and cleaned_str.endswith(')'):
        is_negative = True
        cleaned_str = cleaned_str[1:-1]
    
    try:
        value = float(cleaned_str)
        return value * -1 if is_negative else value
    except (ValueError, TypeError):
        return None

def normalize_table(table_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convierte una única tabla (en un diccionario) de formato Markdown a
    una lista de diccionarios en formato "largo".
    """
    markdown = table_data['corrected_markdown']
    lines = markdown.strip().split('\n')
    
    separator_index = next((i for i, line in enumerate(lines) if '---' in line), -1)
    if separator_index == -1: return []

    header_lines_raw = [line.strip().strip('|').split('|') for line in lines[:separator_index]]
    data_rows_raw = [line.strip().strip('|').split('|') for line in lines[separator_index + 1:]]
    
    if not header_lines_raw or not data_rows_raw: return []

    num_columns = len(header_lines_raw[0])
    column_headers = [' '.join(filter(None, [h[i].strip() for h in header_lines_raw if i < len(h)])) for i in range(num_columns)]

    normalized_rows = []
    for row in data_rows_raw:
        row_label = row[0].strip()
        if not row_label: continue
            
        for i in range(1, len(row)):
            if i < len(column_headers):
                value = clean_numeric_value(row[i])
                if value is not None:
                    normalized_rows.append({
                        "table_name": table_data['table_title'],
                        "row_label": row_label,
                        "column_header": column_headers[i].strip(),
                        "value": value,
                        "currency": 'USD',
                        "page_number": table_data['page_index']
                    })
    return normalized_rows

# --------------------------------------------------------------------------
# --- 3. EJECUCIÓN DEL SCRIPT PRINCIPAL ---
# --------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Iniciando el pipeline completo de PDF a Parquet...")

    # --- FASE 1: INVOCAR EL SCRIPT DE EXTRACCIÓN ---
    print("\n--- FASE 1: Extrayendo y limpiando datos del PDF ---")
    # Llama a la función del otro archivo para obtener los datos estructurados
    structured_tables = process_pdf_to_structured_tables(PDF_INPUT_PATH)

    # --- FASE 2: NORMALIZAR LOS DATOS EXTRAÍDOS ---
    print("\n--- FASE 2: Transformando tablas a formato largo ---")
    all_normalized_rows = []
    for table in structured_tables:
        all_normalized_rows.extend(normalize_table(table))
    print(f"✅ Se generaron {len(all_normalized_rows)} filas de datos en formato largo.")

    # --- FASE 3: GUARDAR EN PARQUET ---
    print("\n--- FASE 3: Guardando resultados en archivo Parquet ---")
    if not all_normalized_rows:
        print("⚠️ No se extrajeron datos numéricos válidos. No se generará el archivo Parquet.")
    else:
        df = pd.DataFrame(all_normalized_rows)
        # Reordenar las columnas para que coincidan con el requerimiento final
        final_columns = [
            'table_name', 'row_label', 'column_header', 
            'value', 'currency', 'page_number'
        ]
        df = df[final_columns]

        # Asegurarse de que el directorio de salida ('silver/') exista
        PARQUET_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Se requiere la librería 'pyarrow'
            # pip install pyarrow
            df.to_parquet(PARQUET_OUTPUT_PATH, index=False)
            print(f"🎉 ¡Éxito! Archivo guardado en: {PARQUET_OUTPUT_PATH}")
            print("\n📊 Muestra de los datos guardados:")
            print(df.head())
        except Exception as e:
            print(f"❌ ERROR: No se pudo guardar el archivo Parquet. Asegúrate de tener 'pyarrow' instalado (`pip install pyarrow`).")
            print(f"Detalle del error: {e}")

    print("\n✅ Proceso finalizado.")
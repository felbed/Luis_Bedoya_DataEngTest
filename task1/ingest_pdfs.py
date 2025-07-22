# === Importación de librerías ===
import os
import re
import hashlib
import aiohttp
import asyncio
import pandas as pd
from datetime import datetime
from tqdm.asyncio import tqdm
from crawl4ai import AsyncWebCrawler, BrowserConfig

# === Constantes de rutas de almacenamiento ===
DATA_ROOT = "task1"
BRONZE_DIR = f"{DATA_ROOT}/bronze"
METADATA_FILE = f"{BRONZE_DIR}/metadata_bronze.parquet"

# === Función para calcular el hash SHA256 de un archivo local ===
def sha256_of_file(path):
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):  # Lee en bloques de 4096 bytes
            sha256.update(chunk)
    return sha256.hexdigest()

# === Función asíncrona para descargar un archivo PDF desde una URL ===
async def download_file(session, url, file_path):
    try:
        async with session.get(url, allow_redirects=True) as response:
            response.raise_for_status()  # Lanza excepción si el estado no es 200
            with open(file_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"[ERROR] No se pudo descargar {url} → {e}")
        return False

# === Procesa una fila del DataFrame: descarga, verifica duplicados y retorna metadata ===
async def process_pdf_row(row, session, existing_hashes):
    name = row["name"].replace(" ", "_")
    url = row["href"]
    quarter = row["quarter"]
    year = row["year"]
    folder_name = f"{year}_{quarter}"
    filename = f"{name}_{quarter}_{year}.pdf"
    folder_path = os.path.join(BRONZE_DIR, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, filename)

    # Descarga el archivo
    downloaded = await download_file(session, url, file_path)
    if not downloaded:
        return None

    # Verifica si el archivo ya existe comparando el hash
    file_hash = sha256_of_file(file_path)
    if file_hash in existing_hashes:
        os.remove(file_path)  # Elimina duplicado
        return None

    # Obtiene tamaño del archivo descargado
    file_size = os.path.getsize(file_path)

    # Retorna registro para la metadata
    return {
        "filename": os.path.relpath(file_path),
        "filesize": file_size,
        "sha256": file_hash,
        "download_timestamp": datetime.utcnow().isoformat()
    }

# === Función principal para ejecutar la descarga masiva y actualizar la metadata ===
async def run_bulk_download_and_metadata(df):
    # Lee metadata previa si existe
    if os.path.exists(METADATA_FILE):
        existing_metadata = pd.read_parquet(METADATA_FILE)
        existing_hashes = set(existing_metadata["sha256"])
    else:
        existing_metadata = pd.DataFrame(columns=["filename", "filesize", "sha256", "download_timestamp"])
        existing_hashes = set()

    new_records = []

    # Crea sesión HTTP para descargas asincrónicas
    async with aiohttp.ClientSession() as session:
        tasks = [
            process_pdf_row(row, session, existing_hashes)
            for _, row in df.iterrows()
        ]
        # Ejecuta descargas con barra de progreso
        for result in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            res = await result
            if res:
                new_records.append(res)

    # Guarda nueva metadata si hay registros nuevos
    if new_records:
        new_df = pd.DataFrame(new_records)
        final_df = pd.concat([existing_metadata, new_df], ignore_index=True)
        final_df.to_parquet(METADATA_FILE, index=False)
        print(f"\n✅ {len(new_df)} nuevos archivos registrados en {METADATA_FILE}")
    else:
        print("\n✅ No hay archivos nuevos para registrar")

# === Extrae los enlaces desde la página web y prepara el DataFrame ===
async def extract_and_prepare_dataframe():
    browser_config = BrowserConfig(headless=True)
    url = "https://www.mineros.com.co/investors/financial-reports"
    keyword = "Consolidated Financial Statements"

    # Inicializa el crawler para obtener todos los enlaces de la página
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url)
        all_links = result.links.get("external", []) + result.links.get("internal", [])
        # Filtra enlaces que sean PDF y contengan la palabra clave
        matching = [
            link for link in all_links
            if link.get("href", "").lower().endswith(".pdf")
            and keyword.lower() in link.get("text", "").lower()
        ]

    # Construye DataFrame con los enlaces válidos
    df = pd.DataFrame(matching)[["href", "text"]]
    df["name"] = keyword
    df["text"] = df["text"].str.replace("\xa0", " ", regex=False).str.strip()

    # Extrae trimestre y año desde el texto
    df[["quarter", "year"]] = df["text"].str.extract(r'(Q\d).*?(\d{4})')

    # Ordena los registros por año y trimestre
    df["year_num"] = df["year"].astype(int)
    df["quarter_num"] = df["quarter"].str.extract(r'Q(\d)')[0].astype(int)
    df = df.sort_values(by=["year_num", "quarter_num"]).reset_index(drop=True)

    # Elimina columnas auxiliares
    df = df.drop(columns=["year_num", "quarter_num"])
    return df

# === Punto de entrada del script ===
if __name__ == "__main__":
    async def main():
        df = await extract_and_prepare_dataframe()         # Extrae información de PDFs
        await run_bulk_download_and_metadata(df)           # Descarga y actualiza metadata

    asyncio.run(main())  # Ejecuta todo el flujo asincrónicamente

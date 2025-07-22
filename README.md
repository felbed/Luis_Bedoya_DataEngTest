# Financial Report Processing Pipeline

Este proyecto implementa un pipeline de datos de punta a punta para extraer, procesar y normalizar tablas de informes financieros en formato PDF. El pipeline utiliza la API de OCR de Mistral AI para la extracción de texto y estructura, y transforma los datos semi-estructurados en un formato analítico limpio (Parquet) siguiendo una arquitectura de capas Medallion (Bronze → Silver).

El proyecto está dividido en tres tareas principales:
- **Task 1:** Ingesta de los archivos PDF fuente.
- **Task 2:** Extracción, limpieza y normalización de las tablas del PDF.
- **Task 3:** Diseño de la arquitectura teórica para la orquestación y despliegue en la nube (Azure).

---

## 📂 Estructura del Proyecto

```
LUIS_BEDOYA_DATAENGTEST/
├── env/
│   └── .env
├── task1/
│   ├── bronze/
│   │   ├── 2021_Q1/
│   │   │   └── Consolidated_Financial_Statements_Q1_2021.pdf
│   │   └── (otros trimestres...)
│   ├── metadata_bronze.parquet
│   └── ingest_pdfs.py
├── task2/
│   ├── silver/
│   │   └── q1_2025_tables.parquet
│   ├── extract_from_pdfs.py
│   └── normalize_tables.py
├── task3/
│   ├── diagram.png
│   └── explanation.md
├── .gitignore
├── environment.yml
└── README.md
```

---

## 🚀 Guía de Ejecución

Sigue estos pasos para configurar el entorno y ejecutar el pipeline.

### Prerrequisitos

- **Conda / Anaconda:** Asegúrate de tener Conda instalado en tu sistema.
- **Python:** La versión 3.9 o superior es recomendada.
- **API Key de Mistral:** Necesitarás una clave de API válida de Mistral AI.

### 1. Configuración del Entorno

1.  **Clonar el Repositorio**
    ```bash
    git clone https://github.com/felbed/Luis_Bedoya_DataEngTest
    cd LUIS_BEDOYA_DATAENGTEST
    ```

2.  **Crear el Entorno de Conda**
    Este comando leerá el archivo `environment.yml` y creará un entorno aislado con todas las dependencias necesarias.
    ```bash
    conda env create -f environment.yml
    ```

3.  **Activar el Entorno**
    Cada vez que trabajes en este proyecto, deberás activar el entorno.
    ```bash
    conda activate financial_pipeline_env
    ```

4.  **Configurar las Credenciales**
    El pipeline requiere una clave de API para acceder a Mistral.
    - Dentro de `env`, crea un archivo llamado `.env`.
    - Añade tu clave de API al archivo `.env` de la siguiente manera:
      ```
      MISTRAL_API_KEY="tu_clave_de_api_aqui"
      ```

### 2. Ejecución de las Tareas

#### ▶️ Task 1 – Ingesta de PDFs

Este script se encarga de descargar los informes financieros y guardarlos en la capa Bronze.

- **Comando de Ejecución:**
  ```bash
  python task1/ingest_pdfs.py
  ```
- **Salida Esperada:**
  - Los archivos PDF se descargarán y organizarán en subdirectorios dentro de `task1/bronze/`.
  - Se creará un archivo de metadatos `task1/metadata_bronze.parquet`.

#### ▶️ Task 2 – Extracción y Normalización de Tablas

Este script es el **punto de entrada principal para el pipeline de procesamiento**. Orquesta la extracción de tablas de un PDF específico (`2025_Q1`), las normaliza a un formato largo y las guarda en la capa Silver.

- **Comando de Ejecución:**
  ```bash
  python task2/normalize_tables.py
  ```
- **Salida Esperada:**
  - El script procesará el archivo `task1/bronze/2025_Q1/Consolidated_Financial_Statements_Q1_2025.pdf`.
  - Se creará un archivo Parquet final en `task2/silver/q1_2025_tables.parquet` que contiene todas las tablas extraídas en formato largo.

---

## ⏱️ Tiempo de Ejecución Estimado

- **Task 1 (`ingest_pdfs.py`):** Aproximadamente **1 - 2 minutos**, dependiendo de la velocidad de la red para las descargas.
- **Task 2 (`normalize_tables.py`):** Aproximadamente **2 - 4 minutos**. El principal cuello de botella es la llamada a la API de OCR de Mistral para procesar el documento de ~26 páginas.

---

## 🏛️ Task 3 – Diseño de Arquitectura

El directorio `task3/` contiene los entregables teóricos de la Tarea 3:
- `explanation.md`: Un documento técnico que detalla la estrategia de orquestación, el diseño de la capa Gold y la arquitectura en la nube de Azure.
- `diagram.png`: Un diagrama visual que ilustra el pipeline completo.
# Desafío 4 - Tratamiento de Señal de Imagen en Sistemas de Comunicaciones

Aplicación integral para el tratamiento, digitalización, transmisión y reconstrucción de señales de imagen a través de esquemas de modulación digital paso banda y canales analógicos ruidosos.

El proyecto implementa un pipeline completo de procesamiento de señales tanto a nivel algorítmico como mediante una interfaz gráfica interactiva desarrollada en **PyQt6**.

---

## 📋 Tabla de Contenido

- [Descripción General](#-descripción-general)
- [Pipeline de Procesamiento](#-pipeline-de-procesamiento)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Protocolo de Trama Digital](#-protocolo-de-trama-digital)
- [Técnicas de Modulación Soportadas](#-técnicas-de-modulación-soportadas)
- [Requisitos e Instalación](#-requisitos-e-instalación)
- [Guía de Uso](#-guía-de-uso)
  - [Modo Procesar (Emisor)](#1-modo-procesar-envía)
  - [Modo Recibir (Receptor)](#2-modo-recibir-compañero)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)

---

## 🔭 Descripción General

Este proyecto aborda el desafío de transmitir información visual (imágenes bidimensionales) a través de canales de comunicación de ancho de banda restringido utilizando señales acústicas moduladas. 

El sistema permite:
1. Aislar elementos de interés mediante segmentación cromática avanzada.
2. Analizar el cumplimiento del criterio de Nyquist para evitar aliasing espacial.
3. Separar la imagen en **capas de color R, G y B** y comprimir cada capa por separado en **WebP**.
4. Empaquetar las capas comprimidas en tramas digitales auto-descriptivas con detección de errores (CRC32).
5. Modular los bits en frecuencias de audio mediante modulaciones digitales (**ASK**, **FSK**, **PSK**).
6. Simular la transmisión por un canal con ruido blanco gaussiano (AWGN).
7. Demodular la señal, validar la integridad de la trama y reconstruir la imagen original, evaluando la calidad mediante métricas cuantitativas (**MSE**, **PSNR** y **BER**).
8. Entregar el resultado al compañero de dos formas: dentro de la señal modulada (**WAV**) o como un **ZIP directo** con las capas WebP para descomprimir y apilar.
9. Sonificar la señal de imagen para percibir la degradación de forma acústica.

---

## ⚙️ Pipeline de Procesamiento

El flujo de procesamiento se divide en 6 etapas secuenciales:

```
[ Imagen Original ]
         │
         ▼
 1. Carga y Filtrado HSV ──────> Aislamiento de rojo dominante y conversión a grises
         │
         ▼
 2. Análisis de Nyquist  ──────> Espectro 2D (FFT), evaluación de aliasing y remuestreo
         │
         ▼
 3. Capas RGB + WebP   ──────> Cuantización a N bits, WebP por capa, cabecera v2 y CRC32
         │
         ▼
 4. Modulación Digital   ──────> Modulación paso banda (ASK / FSK / PSK) a señal WAV
         │
         ▼
 5. Canal Ruidoso (AWGN) ──────> Simulación de ruido según SNR especificado
         │
         ▼
 6. Demodulación & Recon ──────> Umbralización, recuperación de bits, validación CRC32,
                                 reconstrucción matricial y métricas (MSE, PSNR, BER)
```

1. **Carga y Filtro de Rojo Dominante (`core/imagen.py`)**:
   - Corrección automática de rotación EXIF.
   - Segmentación en el espacio de color HSV para detectar tonos rojos (`H ∈ [0, 10] ∪ [170, 180]`).
   - Operaciones morfológicas de apertura y cierre para eliminar ruido granular.
   - Detección de componentes conexas para retener únicamente el objeto rojo de mayor área a color, convirtiendo el resto de la imagen a escala de grises.

2. **Muestreo Espacial y Criterio de Nyquist (`core/nyquist.py`)**:
   - Cálculo de la transformada de Fourier bidimensional (FFT 2D) para evaluar frecuencias espaciales.
   - Determinación de la frecuencia máxima de la imagen y validación del criterio de Nyquist ($f_s \ge 2 f_{max}$).
   - Remuestreo/diezmado espacial bilineal o por área al ancho objetivo seleccionado.

3. **Capas de Color, Compresión y Construcción de Trama (`core/compresion.py`, `core/trama.py`, `core/pipeline.py`)**:
   - Separación de la imagen en tres capas en escala de grises (R, G, B) y cuantización uniforme a $N$ bits por muestra ($2^N$ niveles).
   - Compresión independiente de cada capa en **WebP** (calidad configurable 1-100).
   - Generación de una trama v2 auto-descriptiva: indica dimensiones, número de capas, profundidad, calidad, longitud del payload y CRC32.
   - La lista de niveles cuantizados por capa y los bytes WebP se guardan también como artefactos (`03_digital.bin`, `capa_R.webp`, `capa_G.webp`, `capa_B.webp`).

4. **Modulación Digital y Sonificación (`core/modulacion.py`, `core/audio.py`)**:
   - Mapeo de la trama de bits a señales de audio analógicas muestreadas a $f_s = 44.1\text{ kHz}$.
   - Sonificación del barrido de luminancia de la imagen para inspección auditiva.

5. **Simulación de Canal (`core/modulacion.py`)**:
   - Modelo de canal AWGN aditivo para evaluar la degradación de la señal frente a diferentes relaciones señal-a-ruido (SNR en dB).

6. **Demodulación, Reconstrucción y Métricas (`core/reconstruccion.py`, `core/pipeline.py`)**:
   - Filtrado y cálculo de estadísticos de decisión por bit.
   - Umbralización óptima y recuperación de la secuencia binaria.
   - Parseo de la trama, verificación de suma de comprobación CRC32 y reensamblado de la matriz de píxeles.
   - Cálculo de Tasa de Error de Bit (BER), Error Cuadrático Medio (MSE) y Relación Señal a Ruido de Pico (PSNR).
   - Exportación de resultados en formatos matriciales (PNG) y vectoriales (SVG).

---

## 📁 Estructura del Proyecto

```text
├── core/                       # Lógica central del procesamiento de señal
│   ├── __init__.py
│   ├── audio.py                # Lectura/escritura WAV y sonificación de imágenes
│   ├── compresion.py           # Capas R/G/B y compresión/descompresión WebP
│   ├── constantes.py           # Parámetros del protocolo y encabezado
│   ├── imagen.py               # Carga, corrección EXIF y segmentación HSV
│   ├── modulacion.py           # Modulación (ASK/FSK/PSK), canal AWGN y demodulación
│   ├── nyquist.py              # Espectro 2D, análisis de Nyquist y muestreo
│   ├── pipeline.py             # Orquestador del pipeline (ImageSignalPipeline)
│   ├── reconstruccion.py       # Reconstrucción matricial, métricas MSE/PSNR y gráficas
│   ├── trama.py                # Empaquetado y parseo binario con CRC32
│   └── utils.py                # Conversión de enteros a secuencias de bits
├── gui/                        # Interfaz gráfica de usuario en PyQt6
│   ├── __init__.py
│   ├── main_window.py          # Ventana principal y configuración de pestañas
│   ├── process_tab.py          # Pestaña de procesamiento y emisión
│   ├── receive_tab.py          # Pestaña de recepción y demodulación
│   ├── styles.qss              # Hoja de estilos de la interfaz gráfica
│   ├── widgets.py              # Componentes visuales personalizados
│   └── worker.py               # Hilos en segundo plano (QThread) para no bloquear la UI
├── .gitignore                  # Exclusiones de Git (caché, entornos, salidas)
├── requirements.txt            # Dependencias del proyecto
├── run_gui.py                  # Punto de entrada para ejecutar la aplicación
└── README.md                   # Documentación técnica del proyecto
```

---

## 📡 Protocolo de Trama Digital

### Formato v2 (capas WebP, uso actual)

La trama v2 tiene una cabecera fija de **136 bits** seguida de un payload de longitud variable. Cada capa WebP se precede de su longitud en 32 bits (big-endian) para poder separar las tres capas aunque viajen concatenadas:

| Campo | Longitud | Descripción |
| :--- | :---: | :--- |
| **Sincronización (MAGIC)** | 16 bits | Patrón fijo `0xA5C4` |
| **Versión** | 8 bits | `2` |
| **Ancho ($W$)** | 16 bits | Ancho de la imagen en píxeles |
| **Alto ($H$)** | 16 bits | Alto de la imagen en píxeles |
| **Número de capas** | 8 bits | `3` (R, G, B) |
| **Profundidad ($B$)** | 8 bits | Bits por muestra antes de WebP |
| **Calidad WebP** | 8 bits | Calidad de compresión (1-100) |
| **Bytes de payload** | 32 bits | Longitud total del payload (incluye las longitudes de capa) |
| **Checksum (CRC32)** | 32 bits | Suma de comprobación sobre todo el payload |
| **Payload** | Variable | `[len_R(32) | WebP_R] [len_G(32) | WebP_G] [len_B(32) | WebP_B]` |

### Formato v1 (legacy, RGB sin comprimir)

Se mantiene el parseo de paquetes antiguos con cabecera de **88 bits**: `MAGIC 0xA5C3 | ancho(16) | alto(16) | bits(8) | CRC32(32)` y un payload de $W \times H \times 3 \times B$ bits con las muestras RGB serializadas. El receptor detecta la versión leyendo `meta.json`.

---

## 📶 Técnicas de Modulación Soportadas

El sistema implementa tres esquemas digitales paso banda con tasa de baudios configurable:

1. **ASK (Amplitude Shift Keying)**:
   - Modulación OOK con portadora residual para facilitar la sincronización:
     $$s(t) = (0.25 + 0.75 \cdot b[n]) \cdot \sin(2\pi \cdot 2 f_{baud} \cdot t)$$
   - Demodulación mediante detector de envolvente cuadrático promedio por intervalo de bit.

2. **FSK (Frequency Shift Keying)**:
   - Modulación por desplazamiento de frecuencia de fase continua (CP-FSK):
     - Bit `0`: Frecuencia $f_0 = f_{baud}$ (1 ciclo por bit).
     - Bit `1`: Frecuencia $f_1 = 2 f_{baud}$ (2 ciclos por bit).
   - Demodulación por correlación en cuadratura contra las dos portadoras ortogonales.

3. **PSK (Phase Shift Keying - BPSK)**:
   - Modulación por inversión de fase antipodal:
     $$s(t) = (2 \cdot b[n] - 1) \cdot \sin(2\pi \cdot 2 f_{baud} \cdot t)$$
   - Demodulación coherente por correlación con la portadora de referencia.

---

## 💻 Requisitos e Instalación

### 1. Prerrequisitos
- Python 3.10 o superior instalado.
- Dispositivo de audio habilitado (opcional, para reproducción sonora).

### 2. Clonar el repositorio
```bash
git clone https://github.com/Esteban-G085/Desafio---Tratamientoimagen.git
cd Desafio---Tratamientoimagen
```

### 3. Crear y activar entorno virtual (recomendado)
- **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
- **Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 4. Instalar dependencias
```bash
pip install -r requirements.txt
```

---

## 🚀 Guía de Uso

Inicie la interfaz gráfica ejecutando:

```bash
python run_gui.py
```

### 1. Modo Procesar (Envía)
1. Abra la pestaña **"Procesar (envía)"**.
2. Seleccione la imagen original a transmitir (formatos `.jpg`, `.jpeg`, `.png`, etc.).
3. Configure los parámetros de modulación y muestreo:
   - **Ancho objetivo**: Resolución espacial a la que se remuestreará la imagen (ej. 64 px).
   - **Profundidad de cuantización**: Niveles por capa antes de comprimir (ej. 8 bits).
   - **Esquema de modulación**: ASK, FSK o PSK.
   - **Tasa de baudios**: Velocidad de modulación de símbolos por segundo.
   - **SNR del canal**: Relación señal a ruido en dB (dejar vacío para canal ideal sin ruido).
   - **Entrega al compañero**: `Ambos (WAV + WebP)` (predeterminado), `Solo WAV modulado` o `Solo WebP directo`.
   - **Calidad WebP (%)**: 1-100; valores más bajos reducen el payload (predeterminado 85).
4. Haga clic en **"Procesar imagen"**.
5. Al finalizar se generan, según el flujo elegido:
   ```text
   salida_desafio4/paquete_para_companero.zip   # señal modulada + meta.json (v2)
   salida_desafio4/paquete_comprimido.zip       # capa_R.webp + capa_G.webp + capa_B.webp + meta.json
   ```
   Las capas WebP también se guardan sueltas en `salida_desafio4/` para inspección.

### 2. Modo Recibir (Compañero)
1. Abra la pestaña **"Recibir (compañero)"**.
2. Cargue el ZIP proporcionado por el emisor (`paquete_para_companero.zip` o `paquete_comprimido.zip`).
3. En **"Tipo de paquete recibido"** deje *Detección automática* o elija explícitamente WAV/WebP.
4. Haga clic en **"Procesar recepción"**.
5. El sistema:
   - **Flujo WAV:** extrae la señal, demodula según los metadatos, valida cabecera y CRC32, separa las tres capas WebP y las apila.
   - **Flujo WebP directo:** lee `capa_R.webp`, `capa_G.webp` y `capa_B.webp`, las descomprime y apila sin pasar por el canal modulado.
   - Muestra la imagen reconstruida y guarda `recuperada.png`, `recuperada.svg` y `recuperada_analisis.png`.
   - Con paquetes v1 antiguos mantiene la reconstrucción RGB sin comprimir.

---

## 🛠️ Tecnologías Utilizadas

- **Lenguaje:** [Python 3.10+](https://www.python.org/)
- **Interfaz Gráfica:** [PyQt6](https://riverbankcomputing.com/software/pyqt/)
- **Procesamiento de Imágenes y Visión:** [OpenCV (`opencv-python`)](https://opencv.org/), [Pillow (PIL)](https://python-pillow.org/), formato **WebP** para compresión por capas
- **Cálculo Numérico y Señales:** [NumPy](https://numpy.org/)
- **Visualización y Gráficas:** [Matplotlib](https://matplotlib.org/)
- **Audio y Sonificación:** [SoundDevice](https://python-sounddevice.readthedocs.io/), módulo nativo `wave`


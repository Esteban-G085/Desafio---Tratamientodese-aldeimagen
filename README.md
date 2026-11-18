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
  - [Compresión de imagen](#3-compresión-de-imagen-desafío-4-punto-2)
  - [Pruebas](#4-pruebas)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)

---

## 🔭 Descripción General

Este proyecto aborda el desafío de transmitir información visual (imágenes bidimensionales) a través de canales de comunicación de ancho de banda restringido utilizando señales acústicas moduladas. 

El sistema permite:
1. Aislar elementos de interés mediante segmentación cromática avanzada.
2. Analizar el cumplimiento del criterio de Nyquist para evitar aliasing espacial.
3. Cuantizar y empaquetar la imagen en tramas digitales con detección de errores (CRC32).
4. Modular los bits en frecuencias de audio mediante modulaciones digitales (**ASK**, **FSK**, **PSK**).
5. Simular la transmisión por un canal con ruido blanco gaussiano (AWGN).
6. Demodular la señal, validar la integridad de la trama y reconstruir la imagen original, evaluando la calidad mediante métricas cuantitativas (**MSE**, **PSNR** y **BER**).
7. Sonificar la señal de imagen para percibir la degradación de forma acústica.

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
 3. Cuantización & Trama ──────> Reducción a N bits, cabecera binaria y CRC32
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

3. **Digitalización y Construcción de Trama (`core/trama.py`, `core/pipeline.py`)**:
   - Cuantización uniforme a $N$ bits por muestra ($2^N$ niveles de intensidad).
   - Generación de trama binaria robusta con cabecera de sincronización y código de redundancia cíclica (CRC32).

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
│   ├── compression_common.py   # Texto de cambio de tamaño (ratio / "más grande")
│   ├── compression_image.py    # Compresión WebP lossless → PNG y métricas
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
│   ├── tab_comprimir_imagen.py # Pestaña de compresión de imagen (WebP → PNG)
│   ├── widgets.py              # Componentes visuales personalizados
│   └── worker.py               # Hilos en segundo plano (QThread) para no bloquear la UI
├── tests/                      # Pruebas unitarias (incluye compresión de imagen)
├── .gitignore                  # Exclusiones de Git (caché, entornos, salidas)
├── requirements.txt            # Dependencias del proyecto
├── run_gui.py                  # Punto de entrada para ejecutar la aplicación
└── README.md                   # Documentación técnica del proyecto
```

---

## 📡 Protocolo de Trama Digital

Para garantizar una transmisión confiable y auto-descriptiva, la trama se organiza en una cabecera binaria fija de **88 bits** seguida del payload de la imagen:

| Campo | Longitud | Descripción |
| :--- | :---: | :--- |
| **Sincronización (MAGIC)** | 16 bits | Patrón fijo de inicio de trama (`0xA5C3`) |
| **Ancho ($W$)** | 16 bits | Ancho de la imagen en píxeles |
| **Alto ($H$)** | 16 bits | Alto de la imagen en píxeles |
| **Profundidad de bits ($B$)** | 8 bits | Bits por muestra / nivel de cuantización |
| **Checksum (CRC32)** | 32 bits | Suma de comprobación sobre el payload para validación de integridad |
| **Payload** | $W \times H \times 3 \times B$ bits | Muestras cuantizadas de los canales RGB serializadas |

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
git clone https://github.com/Esteban-G085/Desaf-o---Tratamiento-de-se-al-de-imagen.git
cd Desaf-o---Tratamiento-de-se-al-de-imagen
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
   - **Profundidad de cuantización**: Número de bits por muestra (ej. 8 bits).
   - **Esquema de modulación**: ASK, FSK o PSK.
   - **Tasa de baudios**: Velocidad de modulación de símbolos por segundo.
   - **SNR del canal**: Relación señal a ruido en dB (dejar vacío para canal ideal sin ruido).
4. Haga clic en **"Ejecutar Pipeline"**.
5. Al finalizar, el sistema generará los gráficos analíticos, métricas (BER, MSE, PSNR) y creará automáticamente un archivo comprimido:
   ```text
   salida_desafio4/paquete_para_companero.zip
   ```
   Dicho paquete contiene la señal modulada en audio `.wav` y los metadatos de sincronización `meta.json`.

### 2. Modo Recibir (Compañero)
1. Abra la pestaña **"Recibir (compañero)"**.
2. Cargue el archivo `paquete_para_companero.zip` proporcionado por el emisor.
3. Haga clic en **"Demodular y Reconstruir"**.
4. El sistema:
   - Extraerá la señal modulada.
   - Demodulará los bits según el esquema indicado en los metadatos.
   - Validará la integridad de la cabecera y el CRC32.
   - Mostrará la imagen reconstruida y generará los archivos exportados (`recuperada.png` y `recuperada.svg`).

---

### 3. Compresión de imagen (Desafío 4, punto 2)

En la pestaña **"Compresión de imagen"** se comprime la imagen del Desafío 3
sin pérdida y se verifica la reconstrucción:

1. Pulse **"📂 Elegir imagen"** y seleccione un archivo BMP, PNG, JPG, JPEG o WebP.
2. Deje activada **"Compresión sin pérdida (lossless)"** y pulse
   **"🗜 Comprimir a WebP"**. El archivo `.webp` se guarda en
   `salida_desafio4/compresion_imagen/`.
3. Pulse **"📂 Descomprimir WebP"** para reconstruir la imagen en PNG. Si el
   WebP se generó en la sesión, se compara el SHA-256 de los píxeles y se
   reporta *EXACTA (bit a bit)*.
4. Use **"✅ Verificar"** para comparar píxel a píxel dos imágenes cualesquiera
   (original y reconstruida). Se muestran MAE, RMSE, PSNR, porcentaje de
   píxeles idénticos y el hash SHA-256 de los píxeles.
5. El selector **"Vista"** permite ver *Comparar*, *Original*, *Reconstruida* o
   *Diferencia*. El panel de diferencia muestra `|original − reconstruida| × 8`
   sobre fondo negro; si no hay diferencias aparece el aviso
   *"Sin diferencias (imágenes idénticas)"*.

**Formatos:** se admiten `.bmp`, `.png`, `.jpg`, `.jpeg` y `.webp`. Los `.svg`
son vectoriales: con `cairosvg` instalado se rasterizan automáticamente; si no,
conviértalos a PNG antes de comprimir.

**Nota sobre el ratio:** WebP lossless conserva todos los píxeles. Si la
imagen de origen es JPG/JPEG, el WebP puede salir **más grande** porque el JPG
ya descartó información y el WebP sin pérdida debe almacenar todos los píxeles.
La interfaz lo indica diciendo «archivo X % más grande». Para reducir el tamaño,
use un PNG/BMP como origen o active la compresión con pérdida.

### 4. Pruebas

```bash
python -m unittest discover -s tests -q
```

`tests/test_compression_image.py` cubre el round-trip exacto en RGB y en RGBA
(con transparencia), el rechazo de extensiones no soportadas, la comparación de
imágenes de distinto tamaño y el texto de cambio de tamaño.

---

## 🛠️ Tecnologías Utilizadas

- **Lenguaje:** [Python 3.10+](https://www.python.org/)
- **Interfaz Gráfica:** [PyQt6](https://riverbankcomputing.com/software/pyqt/)
- **Procesamiento de Imágenes y Visión:** [OpenCV (`opencv-python`)](https://opencv.org/), [Pillow (PIL)](https://python-pillow.org/)
- **Cálculo Numérico y Señales:** [NumPy](https://numpy.org/)
- **Visualización y Gráficas:** [Matplotlib](https://matplotlib.org/)
- **Audio y Sonificación:** [SoundDevice](https://python-sounddevice.readthedocs.io/), módulo nativo `wave`

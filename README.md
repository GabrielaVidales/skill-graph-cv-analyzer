# cv-skill-graph

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-lightgrey)](https://flask.palletsprojects.com)
[![Anthropic](https://img.shields.io/badge/Claude-Sonnet_4-purple)](https://anthropic.com)

**Agentes gráficos de IA que extraen competencias de un CV médico y mapean rutas de aprendizaje clínico sobre grafos de conocimiento construidos sobre las taxonomías globales ESCO, O\*NET y SFIA.**

Desarrollado como contribución al proyecto **[Talent Angels @ Learning Tokens](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/80)** de la Linux Foundation Mentorship 2026, con foco en el sector salud latinoamericano y la problemática de fragmentación estructural en el itinerario académico-profesional del talento médico.

---

## Tabla de contenidos

1. [El problema que resuelve](#1-el-problema-que-resuelve)
2. [Qué hace la aplicación](#2-qué-hace-la-aplicación)
3. [Teoría y matemática detrás del sistema](#3-teoría-y-matemática-detrás-del-sistema)
4. [Arquitectura técnica](#4-arquitectura-técnica)
5. [Stack tecnológico](#5-stack-tecnológico)
6. [Estructura del proyecto](#6-estructura-del-proyecto)
7. [Cómo ejecutar localmente](#7-cómo-ejecutar-localmente)
8. [Despliegue en Render](#8-despliegue-en-render)
9. [Hoja de ruta para producción](#9-hoja-de-ruta-para-producción)
10. [Créditos y reconocimientos](#10-créditos-y-reconocimientos)
11. [Licencia](#11-licencia)

---

## 1. El problema que resuelve

El ecosistema de salud en América Latina sufre una **fragmentación estructural** en el itinerario académico-profesional del talento médico: las competencias, certificaciones y experiencia clínica de un profesional no pueden trazarse ni transferirse de manera confiable entre universidad, hospital e industria farmacéutica.

El resultado práctico es devastador:

- La credencialización médica en EUA toma entre 60 y 180 días y cuesta hasta USD $3,500 por proveedor. En México el proceso es análogo pero completamente manual — oficios membretados, PDFs escaneados, firmas autógrafas.
- La industria farmacéutica recruta Investigadores Principales para ensayos clínicos por redes informales porque verificar competencias granulares es operativamente imposible.
- Las competencias adquiridas durante la residencia médica (EPAs, hitos CBME) desaparecen el día de la graduación: el mercado laboral solo ve el nombre de la universidad.
- Ningún competidor regional — LinkedIn, OCC, AuthenticFarma — ofrece verificación primaria de credenciales médicas ni trazabilidad longitudinal.

Este proyecto construye la **capa de inteligencia** que hace legible ese historial: extrae las competencias del CV de un profesional de salud, las ubica en taxonomías globales estandarizadas, mapea sus relaciones en un grafo de conocimiento y calcula rutas de desarrollo hacia las competencias que le faltan.

---

## 2. Qué hace la aplicación

El flujo completo desde la carga del CV hasta el plan de aprendizaje opera en tres pasos:

```
CV (PDF / DOCX)
      │
      ▼
 [Agente LOCATOR]
 Extrae competencias clínicas y técnicas del texto
 y las mapea semánticamente a ESCO / O*NET / SFIA
      │
      ▼
 [Agente CONNECTOR]
 Para cada competencia identificada, mapea:
   · Prerequisitos (qué debía saber antes)
   · Sucesores    (qué puede aprender después)
   · Laterales    (competencias hermanas del mismo nivel)
      │
      ▼
 [Agente PATHFINDER]
 Calcula la ruta óptima en el grafo de conocimiento
 desde las competencias actuales hacia las brechas detectadas
      │
      ▼
 Plan de aprendizaje personalizado (generado por Claude)
 + Grafo SVG interactivo de competencias
```

---

## 3. Teoría y matemática detrás del sistema

### 3.1 Ontología de competencias

Una **ontología** es una representación formal de conceptos y sus relaciones dentro de un dominio. En este sistema, cada competencia es un nodo con propiedades (nombre, fuente taxonómica, nivel, categoría) y relaciones explícitas (qué habilidades la preceden, cuáles habilita). El concepto viene de la Web Semántica y los sistemas expertos de IA simbólica.

Las taxonomías que estructuran el grafo son:

| Taxonomía | Organismo | Cobertura |
|-----------|-----------|-----------|
| **ESCO** | Comisión Europea | Competencias para el mercado laboral europeo |
| **O\*NET** | Dept. de Trabajo EUA | Todas las ocupaciones del mercado norteamericano |
| **SFIA** | SFIA Foundation | Competencias digitales globales |
| **BLS** | Bureau of Labor Statistics | Perspectivas ocupacionales |
| **Lightcast** | Open Skills Network | Lenguaje común de habilidades emergentes |

### 3.2 Grafo de conocimiento: teoría de grafos

El sistema construye un **dígrafo** (grafo dirigido):

```
G = (V, E)
```

Donde **V** es el conjunto de competencias (nodos) y **E** es el conjunto de aristas dirigidas, donde una arista `u → v` significa *"u es prerequisito de v"*.

Esta estructura es un **Grafo Acíclico Dirigido (DAG)**, propiedad que garantiza que no existen ciclos de prerequisitos — no puedes necesitar haber aprendido algo para poder aprenderlo.

**¿Por qué dirigido y no simplemente conectado?** La relación de prerequisito no es simétrica. Que Estadística sea prerequisito de Machine Learning no implica que Machine Learning sea prerequisito de Estadística. La dirección captura causalidad en el aprendizaje.

Este modelo de grafo de conocimiento es el mismo que usa Google Knowledge Graph, Wikidata y la infraestructura semántica de ESCO para relacionar ocupaciones con competencias.

### 3.3 Agente LOCATOR: embeddings y similitud semántica

El Locator recibe texto libre (un CV médico) e identifica qué competencias del catálogo están presentes, aunque no aparezcan con las palabras exactas. Un CV puede decir *"manejo de pacientes post-quirúrgicos en UCI"* y el sistema debe reconocer que eso implica *"Critical Care Nursing"* en la taxonomía ESCO.

Esto es posible gracias a los **embeddings**: representaciones vectoriales de texto en un espacio de alta dimensión donde conceptos semánticamente similares están geométricamente cercanos.

La similitud entre dos conceptos se mide con **similitud coseno**:

```
similitud(A, B) = (A · B) / (‖A‖ × ‖B‖)
```

Donde A y B son vectores de cientos de dimensiones aprendidos durante el preentrenamiento del modelo. Si el ángulo entre ellos es pequeño (coseno → 1), los conceptos son semánticamente equivalentes. El LLM ejecuta esta comparación implícitamente al interpretar el prompt con el catálogo de taxonomías.

En la versión de producción, este paso se reemplazaría por un índice vectorial (FAISS, Pinecone) que consulte directamente los embeddings de ESCO para mayor precisión y velocidad.

### 3.4 Agente CONNECTOR: vecindad en grafos

El Connector implementa la operación de **vecindad** sobre el dígrafo:

```
N⁻(v) = { u ∈ V : (u, v) ∈ E }   ← prerequisitos (vecindad de entrada)
N⁺(v) = { u ∈ V : (v, u) ∈ E }   ← sucesores     (vecindad de salida)
```

Las competencias **laterales** (o hermanas) son aquellas que comparten al menos un prerequisito con el nodo consultado:

```
laterales(v) = { w ∈ V : ∃ u tal que (u,v) ∈ E ∧ (u,w) ∈ E ∧ w ≠ v }
```

Esta operación permite descubrir competencias que el profesional podría adquirir en paralelo dado su conocimiento base actual — por ejemplo, si ya sabe Python y Estadística, puede avanzar hacia Machine Learning *o* hacia Data Analysis de forma independiente.

### 3.5 Agente PATHFINDER: algoritmos de caminos mínimos

El Pathfinder responde la pregunta: *¿cuál es la forma más eficiente de ir de la competencia que tengo a la competencia que necesito?*

Implementa dos algoritmos clásicos de teoría de grafos:

**Búsqueda en Anchura (BFS — Breadth-First Search)**
Explora el grafo nivel por nivel desde el nodo origen. Garantiza encontrar el camino con el **menor número de pasos**. Complejidad temporal: O(V + E).

```
Cola: [origen]
Nivel 0: [Python]
Nivel 1: [Machine Learning, Data Analysis, API Dev]
Nivel 2: [Deep Learning, NLP, Data Viz...]
...hasta llegar al destino
```

**Dijkstra para rutas de mínimo costo**
Cuando las aristas tienen peso (aquí: diferencia de nivel entre competencias consecutivas), Dijkstra garantiza el camino de **mínimo costo total**:

```
Costo(ruta) = Σ |nivel(i+1) − nivel(i)|  para cada paso consecutivo
```

Esta función de costo penaliza los saltos bruscos de nivel, favoreciendo rutas donde el aprendizaje progresa gradualmente. Un salto de nivel 2 a nivel 7 tiene costo 5; pasar por niveles intermedios (2→3→5→7) tiene costo total 5 también pero distribuido en etapas asimilables.

El algoritmo de Dijkstra fue publicado por Edsger Dijkstra en 1959 y sigue siendo el estándar para rutas óptimas en grafos ponderados con pesos no negativos.

### 3.6 Match de competencias: teoría de conjuntos

Cuando se compara un perfil de candidato con los requisitos de una posición, el sistema aplica álgebra de conjuntos:

```
skills_CV  = {A, B, C, D}
skills_JOB = {B, C, E, F}

Intersección = skills_CV ∩ skills_JOB = {B, C}
Brecha       = skills_JOB \ skills_CV  = {E, F}
Bonus        = skills_CV \ skills_JOB  = {A, D}

Match (%) = |intersección| / |skills_JOB| × 100
```

Esta es una forma del **Coeficiente de Jaccard**, métrica estándar de similitud entre conjuntos usada en recuperación de información. La versión ponderada asigna un peso a cada competencia según su importancia relativa en la posición, lo que permite distinguir entre una brecha crítica (cirugía laparoscópica) y una secundaria (Excel avanzado).

### 3.7 El LLM como capa de razonamiento semántico

Un **Large Language Model** es una red neuronal basada en la arquitectura **Transformer** (Vaswani et al., 2017). El mecanismo central es la **atención multi-cabeza**:

```
Attention(Q, K, V) = softmax(QKᵀ / √d) × V
```

Donde Q (queries), K (keys) y V (values) son proyecciones lineales del texto de entrada. La división por √d previene la saturación del softmax cuando la dimensionalidad es alta.

En este sistema el LLM no reemplaza a los algoritmos de grafos — los **complementa**:

| Tarea | Componente | Justificación |
|-------|-----------|---------------|
| Extraer competencias del CV | Claude (LLM) | Requiere comprensión semántica del lenguaje médico |
| Encontrar rutas entre nodos | NetworkX (BFS/Dijkstra) | Determinista, exacto, O(V+E) |
| Calcular porcentaje de match | Python (conjuntos) | Aritmética directa |
| Generar plan de aprendizaje | Claude (LLM) | Requiere síntesis narrativa y contextualización |

Esta separación arquitectónica es deliberada: se le pide a cada componente lo que hace mejor.

---

## 4. Arquitectura técnica

```
┌──────────────────────────────────────────────────────────────┐
│                      cv-skill-graph                           │
│                                                              │
│  ENTRADA                                                     │
│  ┌───────────────────────────────────────┐                   │
│  │  CV Médico  (PDF / DOCX)              │                   │
│  └────────────────────┬──────────────────┘                   │
│                       │                                      │
│                       ▼                                      │
│              ┌─────────────────┐                             │
│              │ Agente LOCATOR  │  ← Claude Sonnet            │
│              │                 │    Extracción semántica      │
│              │ ESCO / O*NET /  │    de competencias médicas  │
│              │ SFIA matching   │                             │
│              └────────┬────────┘                             │
│                       │                                      │
│            ┌──────────┴──────────┐                           │
│            ▼                     ▼                           │
│  ┌──────────────────┐  ┌──────────────────────┐             │
│  │ Agente CONNECTOR │  │  Agente PATHFINDER   │             │
│  │                  │  │                      │             │
│  │ Vecindad N⁻(v)   │  │ BFS / Dijkstra       │             │
│  │ Vecindad N⁺(v)   │  │ Rutas óptimas        │             │
│  │ Laterales        │  │ entre nodos del grafo│             │
│  └──────────────────┘  └──────────────────────┘             │
│                       │                                      │
│                       ▼                                      │
│         ┌─────────────────────────┐                          │
│         │   KNOWLEDGE GRAPH       │                          │
│         │   NetworkX DiGraph      │                          │
│         │   Taxonomías: ESCO,     │                          │
│         │   O*NET, SFIA, BLS      │                          │
│         └─────────────────────────┘                          │
│                       │                                      │
│                       ▼                                      │
│         ┌─────────────────────────┐                          │
│         │   Claude Sonnet (LLM)   │                          │
│         │   Plan de aprendizaje   │                          │
│         │   personalizado         │                          │
│         └─────────────────────────┘                          │
│                       │                                      │
│                       ▼                                      │
│         Grafo SVG + Rutas + Plan (UI Flask)                  │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11 · Flask 3.1 · Gunicorn |
| IA / LLM | Anthropic Claude `claude-sonnet-4-20250514` |
| Motor de grafos | NetworkX 3.4 (dígrafo, BFS, Dijkstra) |
| Parseo de CV | PyPDF2 · python-docx |
| Frontend | HTML/CSS/JS vanilla · SVG renderer propio |
| Contenedor | Docker |
| Despliegue | Render (render.yaml) |

---

## 6. Estructura del proyecto

```
cv-skill-graph/
├── app/
│   └── main.py              # Flask app + 3 agentes + grafo de conocimiento
├── templates/
│   └── index.html           # Interfaz de usuario (drag & drop)
├── static/
│   ├── css/style.css        # Diseño oscuro monospace
│   └── js/app.js            # Lógica frontend + renderer SVG del grafo
├── Dockerfile               # Imagen Docker para Render
├── render.yaml              # Configuración declarativa de Render
├── requirements.txt         # Dependencias Python
└── README.md
```

---

## 7. Cómo ejecutar localmente

### Prerequisitos

- Python 3.11+
- Una API key de Anthropic → [console.anthropic.com](https://console.anthropic.com)

### Instalación

```bash
git clone https://github.com/TU_USUARIO/cv-skill-graph.git
cd cv-skill-graph

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configuración

```bash
# Linux / macOS
export ANTHROPIC_API_KEY=sk-ant-...

# Windows CMD
set ANTHROPIC_API_KEY=sk-ant-...
```

### Ejecutar

```bash
python app/main.py
```

Abre `http://localhost:5000` — arrastra un CV en PDF o DOCX y presiona **Analyze CV**.

---

## 8. Despliegue en Render

### Opción A — render.yaml (recomendado)

1. Haz fork de este repo a tu cuenta de GitHub.
2. En [render.com](https://render.com) → **New** → **Blueprint** → conecta tu repo.
3. Render lee el `render.yaml` automáticamente.
4. Ve a **Environment** en el dashboard → añade `ANTHROPIC_API_KEY = sk-ant-...`
5. Deploy. Tu app queda en `https://cv-skill-graph.onrender.com`.

### Opción B — Web Service manual

1. Render → **New Web Service** → conecta tu repo.
2. Runtime: **Docker**.
3. Variable de entorno: `ANTHROPIC_API_KEY = sk-ant-...`
4. Deploy.

> **Nota plan gratuito:** los servidores free de Render se duermen tras 15 min de inactividad. La primera petición puede tardar ~30 s. Para uso continuo, el plan Starter ($7/mes) mantiene el servidor activo.

---

## 9. Hoja de ruta para producción

El estado actual es un **prototipo funcional**. La ruta hacia un sistema de producción para el sector salud LATAM sigue estos pasos:

### Capa de datos — taxonomías reales

Reemplazar la muestra local por las APIs oficiales:

| Fuente | Endpoint | Autenticación |
|--------|---------|---------------|
| ESCO API | `https://ec.europa.eu/esco/api` | Pública, gratuita |
| O\*NET Web Services | `https://services.onetcenter.org` | Registro gratuito |
| SEP Cédulas Profesionales | `https://contactocedula.sep.gob.mx` | Pública |
| Lightcast Open Skills | `https://lightcast.io/open-skills` | API key |

### Capa de grafo — escala

Migrar de NetworkX (en memoria) a **Neo4j** con el driver `py2neo` para consultas Cypher sobre millones de nodos:

```cypher
MATCH path = shortestPath(
  (a:Skill {name: "Python"})-[:PREREQUISITO*]->(b:Skill {name: "AI Agent Development"})
)
RETURN path
```

### Capa de identidad — credenciales verificables

Integrar la arquitectura de **Identidad Descentralizada (SSI)** del proyecto Learning Tokens original:
- Credenciales verificables en formato W3C VC sobre Hyperledger Fabric
- Wallets médicas donde el profesional custodia sus propias competencias
- Smart Contracts para verificación automática (Proxy Re-Encryption para privacidad)
- Cumplimiento con LFPDPPP (México) y HL7 FHIR para interoperabilidad internacional

### Dominio de salud — ontologías clínicas

Extender las taxonomías con vocabularios médicos estandarizados:
- **SNOMED CT** — terminología clínica internacional
- **HL7 FHIR R4** — recursos `Practitioner`, `PractitionerRole`, `Qualification`
- **CONACEM / SEP** — certificaciones médicas mexicanas
- **EPAs (Actividades Profesionales Confiables)** — marcos CBME para residencias

---

## 10. Créditos y reconocimientos

### Proyecto origen: Learning Tokens

Este trabajo es una implementación derivada y extensión del proyecto **[Learning Tokens](https://github.com/hyperledger-labs/learning-tokens)**, desarrollado durante el Programa de Mentorías de Hyperledger en la Linux Foundation.

**Autores del proyecto Learning Tokens original:**

- **Alfonso Govela** — Mentor, Linux Foundation / Hyperledger Mentorship Program 2023
- **Tanjin Alam** — Mentee, Linux Foundation / Hyperledger Mentorship Program 2023
- **Diana Barrero Zalles** — Head of Research and Sustainability, Global Blockchain Business Council
- **Jackson Ross** — Technical Program Lead, Global Blockchain Business Council

El README original del proyecto Learning Tokens, el modelo conceptual de tokens de aprendizaje sobre el Token Taxonomy Framework (IWA/TTF), y la arquitectura de credenciales verificables son obra de estos autores y están licenciados bajo Apache 2.0.

Repositorio original: [https://github.com/hyperledger-labs/learning-tokens](https://github.com/hyperledger-labs/learning-tokens)

### Proyecto Talent Angels (marco institucional)

Esta implementación forma parte de **Talent Angels @ Learning Tokens**, mentorship de la Linux Foundation 2026:

- Más información: [LF Mentorship Issue #80](https://github.com/LF-Decentralized-Trust-Mentorships/mentorship-program/issues/80)
- Código de conducta: [lfdecentralizedtrust.org/code-of-conduct](https://www.lfdecentralizedtrust.org/code-of-conduct)

### Contexto de investigación

La problemática de fragmentación estructural del talento en salud LATAM documentada en este repositorio está respaldada por análisis de mercado que citan trabajos de:

- Jayaraman et al. (2022) — *Trustworthy Healthcare Professional Credential Verification using Blockchain Technology*, IEEE Access, Khalifa University
- Gordon & Catalini (2018) — *Blockchain Technology for Healthcare: Facilitating the Transition to Patient-Driven Interoperability*, MIT
- Usman, Kallhoff & Khurshid (2021) — *The Case for Establishing a Blockchain R&D Program at an Academic Medical Center*, Blockchain in Healthcare Today

---

## 11. Licencia

Apache 2.0 — ver archivo [LICENSE](./LICENSE).

---

*cv-skill-graph · Contribución al proyecto Learning Tokens · Linux Foundation · 2026*

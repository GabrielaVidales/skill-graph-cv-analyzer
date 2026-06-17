"""
main.py — HealthSkill Graph · Backend
======================================
Aquí vive todo el server. Flask maneja las rutas,
los tres agentes (Locator, Connector, Pathfinder) hacen el trabajo duro,
y Claude actúa como el cerebro que lee texto médico y lo convierte en estructura.

Si algo explota, primero revisa que ANTHROPIC_API_KEY esté configurada en Render.
"""

import os, json, re, io, base64
import networkx as nx
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import anthropic

# Intentamos importar parsers de documentos — si no están, el servidor igual arranca
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

# ── App setup ──────────────────────────────────────────────────────────────
# Templates están en ../templates/, no hay carpeta static porque todo el CSS/JS
# va embebido en el HTML (así lo quiso el jefe)
app = Flask(__name__, template_folder=".", static_folder=".", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB máximo por archivo

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}

# El cliente de Anthropic lee la key del entorno — NO la pongas en el código
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ── Taxonomía médica ────────────────────────────────────────────────────────
# Esta es nuestra "base de datos" de competencias médicas.
# Basada en ESCO (EU), O*NET (USA) y SFIA (global digital skills).
# Cada habilidad tiene: nombre, fuente, categoría, nivel (1=básico, 7=experto),
# prerequisitos (pre) y lo que desbloquea (suc = sucesores).
# En producción esto vendría de las APIs reales de ESCO y O*NET.
TAXONOMY = {
    # ── FUNDAMENTOS ─────────────────────────────────────────────────────
    "M001": {"name": "Medical Sciences Fundamentals", "source": "ESCO",  "cat": "Foundation",     "level": 1, "pre": [],              "suc": ["M002", "M003", "M010"]},
    "M002": {"name": "Anatomy & Physiology",           "source": "ESCO",  "cat": "Foundation",     "level": 2, "pre": ["M001"],        "suc": ["M004", "M005", "M006"]},
    "M003": {"name": "Medical Ethics & Bioethics",     "source": "ONET",  "cat": "Foundation",     "level": 2, "pre": ["M001"],        "suc": ["M015", "M020"]},
    "M010": {"name": "Evidence-Based Medicine",        "source": "ESCO",  "cat": "Foundation",     "level": 3, "pre": ["M001"],        "suc": ["M011", "M016"]},

    # ── HABILIDADES CLÍNICAS ─────────────────────────────────────────────
    "M004": {"name": "Physical Examination",           "source": "ESCO",  "cat": "Clinical Skills","level": 3, "pre": ["M002"],        "suc": ["M005", "M007"]},
    "M005": {"name": "Clinical Diagnosis",             "source": "ESCO",  "cat": "Clinical Skills","level": 4, "pre": ["M002", "M004"],"suc": ["M006", "M008"]},
    "M006": {"name": "Emergency Medicine",             "source": "ONET",  "cat": "Clinical Skills","level": 5, "pre": ["M002", "M005"],"suc": ["M009"]},
    "M007": {"name": "Patient Communication",          "source": "ESCO",  "cat": "Clinical Skills","level": 3, "pre": ["M004"],        "suc": ["M015", "M020"]},
    "M008": {"name": "Internal Medicine",              "source": "ONET",  "cat": "Clinical Skills","level": 5, "pre": ["M005"],        "suc": ["M009", "M013"]},
    "M009": {"name": "ICU & Critical Care",            "source": "ESCO",  "cat": "Clinical Skills","level": 6, "pre": ["M006", "M008"],"suc": ["M014"]},

    # ── CIRUGÍA ──────────────────────────────────────────────────────────
    "M011": {"name": "Surgical Fundamentals",          "source": "ESCO",  "cat": "Surgery",        "level": 4, "pre": ["M010"],        "suc": ["M012", "M013"]},
    "M012": {"name": "Laparoscopic Surgery",           "source": "ESCO",  "cat": "Surgery",        "level": 6, "pre": ["M011"],        "suc": ["M014"]},
    "M013": {"name": "Post-operative Care",            "source": "ONET",  "cat": "Surgery",        "level": 5, "pre": ["M008", "M011"],"suc": ["M014"]},
    "M014": {"name": "Surgical Specialization",        "source": "ESCO",  "cat": "Surgery",        "level": 7, "pre": ["M012", "M013", "M009"], "suc": []},

    # ── INVESTIGACIÓN ─────────────────────────────────────────────────────
    "M015": {"name": "Clinical Research Methods",      "source": "ESCO",  "cat": "Research",       "level": 4, "pre": ["M003", "M007"],"suc": ["M016", "M017"]},
    "M016": {"name": "Clinical Trial Management",      "source": "ONET",  "cat": "Research",       "level": 5, "pre": ["M010", "M015"],"suc": ["M018", "M019"]},
    "M017": {"name": "Biostatistics",                  "source": "ESCO",  "cat": "Research",       "level": 5, "pre": ["M015"],        "suc": ["M018"]},
    "M018": {"name": "Principal Investigator",         "source": "ONET",  "cat": "Research",       "level": 7, "pre": ["M016", "M017"],"suc": []},
    "M019": {"name": "Regulatory Affairs (COFEPRIS/FDA)", "source": "ESCO","cat": "Research",      "level": 6, "pre": ["M016"],        "suc": ["M018"]},

    # ── SALUD DIGITAL ─────────────────────────────────────────────────────
    "M020": {"name": "Health Informatics",             "source": "SFIA",  "cat": "Digital Health", "level": 3, "pre": ["M003", "M007"],"suc": ["M021", "M022"]},
    "M021": {"name": "Electronic Health Records",      "source": "SFIA",  "cat": "Digital Health", "level": 4, "pre": ["M020"],        "suc": ["M023"]},
    "M022": {"name": "Telemedicine",                   "source": "SFIA",  "cat": "Digital Health", "level": 4, "pre": ["M020"],        "suc": ["M023"]},
    "M023": {"name": "AI in Clinical Decision Support","source": "SFIA",  "cat": "Digital Health", "level": 6, "pre": ["M021", "M022"],"suc": []},

    # ── GESTIÓN ───────────────────────────────────────────────────────────
    "M024": {"name": "Hospital Administration",        "source": "ONET",  "cat": "Management",     "level": 5, "pre": ["M003"],        "suc": ["M025"]},
    "M025": {"name": "Healthcare Quality & Patient Safety","source": "ONET","cat": "Management",   "level": 6, "pre": ["M024"],        "suc": []},
}

# Colores por categoría — se usan en el grafo SVG del frontend
CAT_COLORS = {
    "Foundation":     "#3b82f6",
    "Clinical Skills":"#10b981",
    "Surgery":        "#ec4899",
    "Research":       "#f59e0b",
    "Digital Health": "#8b5cf6",
    "Management":     "#ef4444",
}

# ── Construcción del grafo de conocimiento ──────────────────────────────────
# NetworkX DiGraph = grafo dirigido donde u→v significa "u es prerequisito de v"
# Esto es teoría de grafos clásica: G = (V, E) con V=habilidades, E=relaciones
def build_graph():
    G = nx.DiGraph()
    for sid, d in TAXONOMY.items():
        G.add_node(sid, **d)
    for sid, d in TAXONOMY.items():
        for sucesor in d["suc"]:
            if sucesor in TAXONOMY:
                G.add_edge(sid, sucesor)
    return G

GRAPH = build_graph()


# ── Helpers básicos ─────────────────────────────────────────────────────────

def allowed(filename):
    """Verifica que el archivo sea PDF o DOCX — nada más."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text(file_bytes, filename):
    """
    Saca el texto de un PDF o DOCX.
    Ojo: no funciona con PDFs escaneados (imágenes) — para eso necesitarías OCR.
    """
    ext = filename.rsplit(".", 1)[1].lower()
    if ext == "pdf" and PyPDF2:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "".join(page.extract_text() or "" for page in reader.pages)
    if ext in ("doc", "docx") and DocxDocument:
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


def call_claude(system_prompt, user_message, max_tokens=2000):
    """
    Llama a Claude con un system prompt y un mensaje de usuario.
    Aquí es donde gastamos tokens — úsalo con criterio.
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    return response.content[0].text


def parse_json_safe(raw_text):
    """
    Intenta parsear JSON de la respuesta de Claude.
    Claude a veces envuelve el JSON en ```json ... ``` así que lo limpiamos primero.
    """
    clean = re.sub(r"```json|```", "", raw_text).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {}


# ── AGENTE 1: LOCATOR ───────────────────────────────────────────────────────
def agent_locator(text, mode="cv"):
    """
    El Locator lee texto libre (CV o descripción de puesto) y mapea
    semánticamente las habilidades mencionadas a nuestra taxonomía médica.

    Usa embeddings implícitos del LLM — si el CV dice "manejo de UCI"
    el modelo entiende que eso es M009 (ICU & Critical Care).
    """
    # Le pasamos todo el catálogo al modelo para que haga el matching
    catalog_str = json.dumps({
        k: {"name": v["name"], "cat": v["cat"], "level": v["level"]}
        for k, v in TAXONOMY.items()
    })

    document_type = "CV of a healthcare professional" if mode == "cv" else "Job description / position requirements"

    system = f"""You are the Locator agent of a medical skills knowledge graph.
Analyze the {document_type} and identify which skills from the catalog are present.
Use semantic matching — "manejo de UCI" matches "ICU & Critical Care", etc.

MEDICAL SKILLS CATALOG:
{catalog_str}

Reply ONLY with valid JSON, no extra text:
{{
  "skills": [{{"id":"M001","name":"...","level":N,"confidence":N,"evidence":"brief text snippet showing why"}}],
  "unmapped": ["skills or experience mentioned but not in our taxonomy"],
  "profile_summary": "2-sentence professional summary"
}}"""

    raw = call_claude(system, text[:4000])
    return parse_json_safe(raw)


# ── AGENTE 2: CONNECTOR ─────────────────────────────────────────────────────
def agent_connector(skill_ids):
    """
    Para cada habilidad identificada, mapea su vecindad en el grafo:
    - N⁻(v) = prerequisitos (qué necesitabas saber antes)
    - N⁺(v) = sucesores (qué puedes aprender después)
    - Laterales = habilidades hermanas (mismo prerequisito)

    Matemáticamente: vecindad de entrada y salida en el dígrafo.
    """
    results = {}
    for sid in skill_ids:
        if sid not in GRAPH:
            continue

        node_data = TAXONOMY[sid]
        predecessors = list(GRAPH.predecessors(sid))
        successors = list(GRAPH.successors(sid))

        # Habilidades laterales: comparten al menos un prerequisito con este nodo
        laterals = set()
        for pred in predecessors:
            for sibling in GRAPH.successors(pred):
                if sibling != sid:
                    laterals.add(sibling)

        def enrich(id_list):
            return [
                {"id": i, "name": TAXONOMY[i]["name"], "level": TAXONOMY[i]["level"]}
                for i in id_list if i in TAXONOMY
            ]

        results[sid] = {
            "skill":         {"id": sid, "name": node_data["name"], "level": node_data["level"]},
            "prerequisites": enrich(predecessors),
            "next_skills":   enrich(successors),
            "lateral":       enrich(list(laterals)[:4])
        }
    return results


# ── AGENTE 3: PATHFINDER ────────────────────────────────────────────────────
def agent_pathfinder(have_ids, want_ids):
    """
    Calcula la ruta más corta en el grafo de conocimiento entre las habilidades
    que tiene el candidato y las que le faltan.

    Usa BFS (Breadth-First Search) de NetworkX — O(V+E) de complejidad.
    Para cada habilidad faltante, busca el camino más corto desde cualquier
    habilidad que ya tenga el candidato.
    """
    G_undirected = GRAPH.to_undirected()  # Para buscar en ambas direcciones
    paths = {}

    for target_id in want_ids:
        best_path = None
        best_length = float("inf")

        for source_id in have_ids:
            if source_id == target_id:
                continue
            if source_id not in GRAPH or target_id not in GRAPH:
                continue
            try:
                path = nx.shortest_path(G_undirected, source_id, target_id)
                if len(path) < best_length:
                    best_length = len(path)
                    best_path = {
                        "from": TAXONOMY[source_id]["name"],
                        "to":   TAXONOMY[target_id]["name"],
                        "steps": [
                            {"id": s, "name": TAXONOMY[s]["name"], "level": TAXONOMY[s]["level"]}
                            for s in path
                        ],
                        "length": len(path)
                    }
            except nx.NetworkXNoPath:
                pass  # No hay conexión entre estos dos nodos — normal

        if best_path:
            paths[target_id] = best_path

    return paths


# ── Plan de aprendizaje con IA ───────────────────────────────────────────────
def generate_learning_plan(cv_profile, jd_profile, gap_ids, paths):
    """
    Claude genera un plan de aprendizaje real, con recursos médicos concretos
    (ENARM, CONACEM, UpToDate, PubMed, etc.) basado en las brechas detectadas.
    """
    gap_names = [TAXONOMY[g]["name"] for g in gap_ids if g in TAXONOMY]

    system = """You are a senior medical career advisor specializing in LATAM healthcare.
Write a clear, motivating, actionable learning plan in the same language the input documents use.

Structure your response exactly like this:
## Resumen
(2-3 sentences overview)

## Fase 1 — Fundamentos (Meses 1-3)
(skills + specific resources)

## Fase 2 — Desarrollo (Meses 4-8)
(skills + specific resources)

## Fase 3 — Especialización (Meses 9-12)
(skills + specific resources)

## Recursos Clave
(ENARM, CONACEM, UpToDate, PubMed, residency programs as applicable)

Be concrete. Max 500 words. Mention real Mexican/LATAM resources when relevant."""

    user = f"""Candidate profile: {cv_profile}
Position requirements: {jd_profile}
Skills to develop: {gap_names}
Available graph paths: {json.dumps(paths, ensure_ascii=False)}"""

    return call_claude(system, user, max_tokens=1200)


# ── Match analysis ───────────────────────────────────────────────────────────
def analyze_match(cv_skill_ids, jd_skill_ids):
    """
    Álgebra de conjuntos pura:
    - matched  = CV ∩ JD  (tiene lo que piden)
    - missing  = JD \ CV  (le falta esto)
    - bonus    = CV \ JD  (tiene esto de extra)
    - pct      = |matched| / |JD| × 100  (Jaccard simplificado)
    """
    matched = [i for i in jd_skill_ids if i in cv_skill_ids]
    missing = [i for i in jd_skill_ids if i not in cv_skill_ids]
    bonus   = [i for i in cv_skill_ids  if i not in jd_skill_ids]
    pct     = round(len(matched) / len(jd_skill_ids) * 100, 1) if jd_skill_ids else 0
    return matched, missing, bonus, pct


# ── Construcción de datos para el grafo SVG ──────────────────────────────────
def build_graph_data(cv_ids, jd_ids, paths):
    """
    Prepara los nodos y aristas relevantes para visualizar en el frontend.
    Solo incluimos los nodos que aparecen en el análisis, no todo el grafo.
    """
    relevant_ids = set(cv_ids) | set(jd_ids)
    for path_data in paths.values():
        for step in path_data["steps"]:
            relevant_ids.add(step["id"])

    nodes, edges = [], []
    for sid in relevant_ids:
        if sid not in TAXONOMY:
            continue
        nodes.append({
            "id":       sid,
            "label":    TAXONOMY[sid]["name"],
            "level":    TAXONOMY[sid]["level"],
            "cat":      TAXONOMY[sid]["cat"],
            "color":    CAT_COLORS.get(TAXONOMY[sid]["cat"], "#888"),
            "owned":    sid in cv_ids,
            "required": sid in jd_ids
        })
        for successor in GRAPH.successors(sid):
            if successor in relevant_ids:
                edges.append({"from": sid, "to": successor})

    return {"nodes": nodes, "edges": edges}


# ── RUTAS FLASK ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/preview-cv", methods=["POST"])
def preview_cv():
    """
    Endpoint nuevo: recibe el archivo del CV y devuelve su texto extraído
    para mostrarlo en la pestaña del candidato antes de analizar.
    También devuelve un base64 del PDF para el preview embebido.
    """
    file = request.files.get("cv")
    if not file or not allowed(file.filename):
        return jsonify({"error": "Archivo inválido"}), 400

    file_bytes = file.read()
    filename   = secure_filename(file.filename)
    text       = extract_text(file_bytes, filename)

    # Base64 para preview embebido (solo PDFs)
    ext = filename.rsplit(".", 1)[1].lower()
    pdf_base64 = None
    if ext == "pdf":
        pdf_base64 = base64.b64encode(file_bytes).decode("utf-8")

    return jsonify({
        "text":        text[:3000],  # Solo primeros 3000 chars para el preview
        "word_count":  len(text.split()),
        "filename":    filename,
        "pdf_base64":  pdf_base64
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Endpoint principal: orquesta los 3 agentes y devuelve todos los resultados.
    El frontend los distribuye en las 3 pestañas.
    """
    cv_file       = request.files.get("cv")
    jd_file       = request.files.get("jd")
    jd_text_input = request.form.get("jd_text", "").strip()

    # Validación mínima — el CV es obligatorio
    if not cv_file or not allowed(cv_file.filename):
        return jsonify({"error": "Por favor sube un CV válido (PDF o DOCX)."}), 400

    cv_bytes = cv_file.read()
    cv_text  = extract_text(cv_bytes, secure_filename(cv_file.filename))

    if len(cv_text) < 50:
        return jsonify({"error": "No se pudo extraer texto del CV. ¿Es un PDF escaneado?"}), 422

    # La descripción de puesto puede venir como archivo o como texto pegado
    jd_text = ""
    if jd_file and jd_file.filename and allowed(jd_file.filename):
        jd_text = extract_text(jd_file.read(), secure_filename(jd_file.filename))
    elif jd_text_input:
        jd_text = jd_text_input

    # ── AGENTE 1: Locator ──────────────────────────────────────────────
    cv_result = agent_locator(cv_text, "cv")
    cv_ids    = [s["id"] for s in cv_result.get("skills", []) if s["id"] in TAXONOMY]

    jd_result, jd_ids = {}, []
    if jd_text:
        jd_result = agent_locator(jd_text, "jd")
        jd_ids    = [s["id"] for s in jd_result.get("skills", []) if s["id"] in TAXONOMY]

    # ── AGENTE 2: Connector ────────────────────────────────────────────
    connections = agent_connector(cv_ids)

    # Brechas = habilidades que el candidato no tiene pero podría aprender
    # Si hay JD: brechas = lo que pide el puesto y no tiene el candidato
    # Si no hay JD: brechas = sucesores directos en el grafo
    if jd_ids:
        gaps = [i for i in jd_ids if i not in cv_ids][:6]
    else:
        all_reachable = {s for sid in cv_ids for s in GRAPH.successors(sid)} - set(cv_ids)
        gaps = list(all_reachable)[:6]

    # ── AGENTE 3: Pathfinder ───────────────────────────────────────────
    paths = agent_pathfinder(cv_ids, gaps)

    # ── Match analysis ────────────────────────────────────────────────
    matched, missing, bonus, match_pct = [], [], [], None
    if jd_ids:
        matched, missing, bonus, match_pct = analyze_match(cv_ids, jd_ids)

    # ── Plan de aprendizaje ───────────────────────────────────────────
    plan = generate_learning_plan(
        cv_result.get("profile_summary", ""),
        jd_result.get("profile_summary", "") if jd_result else "No se proporcionó descripción de puesto",
        gaps,
        paths
    )

    # ── Datos del grafo ───────────────────────────────────────────────
    graph_data = build_graph_data(cv_ids, jd_ids, paths)

    def enrich(id_list):
        return [
            {"id": i, "name": TAXONOMY[i]["name"], "level": TAXONOMY[i]["level"], "cat": TAXONOMY[i]["cat"]}
            for i in id_list if i in TAXONOMY
        ]

    return jsonify({
        # Resúmenes
        "cv_summary":    cv_result.get("profile_summary", ""),
        "jd_summary":    jd_result.get("profile_summary", "") if jd_result else "",
        # Skills
        "cv_skills":     cv_result.get("skills", []),
        "jd_skills":     jd_result.get("skills", []) if jd_result else [],
        "unmapped":      cv_result.get("unmapped", []),
        # Match
        "gaps":          enrich(gaps),
        "matched":       enrich(matched),
        "missing":       enrich(missing),
        "bonus":         enrich(bonus),
        "match_pct":     match_pct,
        # Rutas y plan
        "paths":         paths,
        "learning_plan": plan,
        # Grafo
        "graph":         graph_data,
        # Flag para el frontend
        "has_jd":        bool(jd_text),
    })


# ── Arranque ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

import os, json, re, io
import networkx as nx
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import anthropic

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
ALLOWED = {"pdf", "doc", "docx"}
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ── Medical Taxonomy (ESCO / O*NET / SFIA health domains) ──────────────────
TAXONOMY = {
    # Foundation
    "M001": {"name":"Medical Sciences Fundamentals","source":"ESCO","cat":"Foundation","level":1,"pre":[],"suc":["M002","M003","M010"]},
    "M002": {"name":"Anatomy & Physiology","source":"ESCO","cat":"Foundation","level":2,"pre":["M001"],"suc":["M004","M005","M006"]},
    "M003": {"name":"Medical Ethics & Bioethics","source":"ONET","cat":"Foundation","level":2,"pre":["M001"],"suc":["M015","M020"]},
    "M010": {"name":"Evidence-Based Medicine","source":"ESCO","cat":"Foundation","level":3,"pre":["M001"],"suc":["M011","M016"]},

    # Clinical
    "M004": {"name":"Physical Examination","source":"ESCO","cat":"Clinical Skills","level":3,"pre":["M002"],"suc":["M005","M007"]},
    "M005": {"name":"Clinical Diagnosis","source":"ESCO","cat":"Clinical Skills","level":4,"pre":["M002","M004"],"suc":["M006","M008"]},
    "M006": {"name":"Emergency Medicine","source":"ONET","cat":"Clinical Skills","level":5,"pre":["M002","M005"],"suc":["M009"]},
    "M007": {"name":"Patient Communication","source":"ESCO","cat":"Clinical Skills","level":3,"pre":["M004"],"suc":["M015","M020"]},
    "M008": {"name":"Internal Medicine","source":"ONET","cat":"Clinical Skills","level":5,"pre":["M005"],"suc":["M009","M013"]},
    "M009": {"name":"ICU & Critical Care","source":"ESCO","cat":"Clinical Skills","level":6,"pre":["M006","M008"],"suc":["M014"]},

    # Surgical
    "M011": {"name":"Surgical Fundamentals","source":"ESCO","cat":"Surgery","level":4,"pre":["M010"],"suc":["M012","M013"]},
    "M012": {"name":"Laparoscopic Surgery","source":"ESCO","cat":"Surgery","level":6,"pre":["M011"],"suc":["M014"]},
    "M013": {"name":"Post-operative Care","source":"ONET","cat":"Surgery","level":5,"pre":["M008","M011"],"suc":["M014"]},
    "M014": {"name":"Surgical Specialization","source":"ESCO","cat":"Surgery","level":7,"pre":["M012","M013","M009"],"suc":[]},

    # Research
    "M015": {"name":"Clinical Research Methods","source":"ESCO","cat":"Research","level":4,"pre":["M003","M007"],"suc":["M016","M017"]},
    "M016": {"name":"Clinical Trial Management","source":"ONET","cat":"Research","level":5,"pre":["M010","M015"],"suc":["M018","M019"]},
    "M017": {"name":"Biostatistics","source":"ESCO","cat":"Research","level":5,"pre":["M015"],"suc":["M018"]},
    "M018": {"name":"Principal Investigator","source":"ONET","cat":"Research","level":7,"pre":["M016","M017"],"suc":[]},
    "M019": {"name":"Regulatory Affairs (COFEPRIS/FDA)","source":"ESCO","cat":"Research","level":6,"pre":["M016"],"suc":["M018"]},

    # Digital Health
    "M020": {"name":"Health Informatics","source":"SFIA","cat":"Digital Health","level":3,"pre":["M003","M007"],"suc":["M021","M022"]},
    "M021": {"name":"Electronic Health Records","source":"SFIA","cat":"Digital Health","level":4,"pre":["M020"],"suc":["M023"]},
    "M022": {"name":"Telemedicine","source":"SFIA","cat":"Digital Health","level":4,"pre":["M020"],"suc":["M023"]},
    "M023": {"name":"AI in Clinical Decision Support","source":"SFIA","cat":"Digital Health","level":6,"pre":["M021","M022"],"suc":[]},

    # Management
    "M024": {"name":"Hospital Administration","source":"ONET","cat":"Management","level":5,"pre":["M003"],"suc":["M025"]},
    "M025": {"name":"Healthcare Quality & Patient Safety","source":"ONET","cat":"Management","level":6,"pre":["M024"],"suc":[]},
}

OCCUPATIONS = {
    "29-1216.00": {"title":"General Practitioner","skills":["M004","M005","M007","M008"],"min_level":4},
    "29-1067.00": {"title":"Surgeon","skills":["M011","M012","M013","M009"],"min_level":6},
    "29-1228.00": {"title":"ICU Specialist","skills":["M006","M008","M009"],"min_level":6},
    "29-1071.00": {"title":"Clinical Researcher / PI","skills":["M015","M016","M017","M018"],"min_level":5},
    "11-9111.00": {"title":"Hospital Medical Director","skills":["M005","M024","M025","M003"],"min_level":6},
    "29-1299.02": {"title":"Digital Health Specialist","skills":["M020","M021","M022","M023"],"min_level":4},
}

def build_graph():
    G = nx.DiGraph()
    for sid, d in TAXONOMY.items():
        G.add_node(sid, **d)
    for sid, d in TAXONOMY.items():
        for s in d["suc"]:
            if s in TAXONOMY:
                G.add_edge(sid, s)
    return G

GRAPH = build_graph()

CAT_COLORS = {
    "Foundation":     "#60a5fa",
    "Clinical Skills":"#4ade80",
    "Surgery":        "#f472b6",
    "Research":       "#fb923c",
    "Digital Health": "#a78bfa",
    "Management":     "#facc15",
}

def allowed(fn): return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED

def extract_text(file_bytes, filename):
    ext = filename.rsplit(".",1)[1].lower()
    if ext == "pdf" and PyPDF2:
        r = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "".join(p.extract_text() or "" for p in r.pages)
    if ext in ("doc","docx") and DocxDocument:
        doc = DocxDocument(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""

def call_claude(system, user, max_tokens=2000):
    r = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role":"user","content":user}]
    )
    return r.content[0].text

def parse_json(raw):
    raw = re.sub(r"```json|```","",raw).strip()
    try: return json.loads(raw)
    except: return {}

def locator(text, mode="cv"):
    catalog = json.dumps({k:{"name":v["name"],"cat":v["cat"],"level":v["level"]} for k,v in TAXONOMY.items()})
    prefix = "CV of a healthcare professional" if mode=="cv" else "Job description / position requirements"
    system = f"""You are the Locator agent of a medical skills graph system.
Analyze the {prefix} and identify which skills from the catalog are present (exact or semantic match).
MEDICAL SKILLS CATALOG: {catalog}
Reply ONLY with valid JSON:
{{"skills":[{{"id":"M001","name":"...","level":N,"confidence":N,"evidence":"brief snippet"}}],
"unmapped":["skills mentioned but not in catalog"],
"profile_summary":"2-sentence summary"}}"""
    raw = call_claude(system, text[:4000])
    return parse_json(raw)

def connector(skill_ids):
    results = {}
    for sid in skill_ids:
        if sid not in GRAPH: continue
        node = TAXONOMY[sid]
        preds = list(GRAPH.predecessors(sid))
        succs = list(GRAPH.successors(sid))
        laterals = set()
        for p in preds:
            for s in GRAPH.successors(p):
                if s != sid: laterals.add(s)
        def e(ids): return [{"id":i,"name":TAXONOMY[i]["name"],"level":TAXONOMY[i]["level"]} for i in ids if i in TAXONOMY]
        results[sid] = {"skill":{"id":sid,"name":node["name"],"level":node["level"]},
                        "prerequisites":e(preds),"next_skills":e(succs),"lateral":e(list(laterals)[:4])}
    return results

def pathfinder(have, want):
    G_ud = GRAPH.to_undirected()
    paths = {}
    for target in want:
        best, best_cost = None, float("inf")
        for src in have:
            if src == target or src not in GRAPH or target not in GRAPH: continue
            try:
                path = nx.shortest_path(G_ud, src, target)
                if len(path) < best_cost:
                    best_cost = len(path)
                    best = {"from":TAXONOMY[src]["name"],"to":TAXONOMY[target]["name"],
                            "steps":[{"id":s,"name":TAXONOMY[s]["name"],"level":TAXONOMY[s]["level"]} for s in path],
                            "length":len(path)}
            except nx.NetworkXNoPath: pass
        if best: paths[target] = best
    return paths

def learning_plan(profile_cv, profile_jd, gaps, paths):
    gap_names = [TAXONOMY[g]["name"] for g in gaps if g in TAXONOMY]
    system = """You are a senior medical career advisor. Write a clear, motivating, actionable learning plan
in the same language the documents are written in.
Structure: Overview → Phase 1 → Phase 2 → Phase 3 (skills, resources, timeline per phase) → Closing.
Be concrete about medical resources (ENARM, CONACEM, UpToDate, PubMed, residency programs). Max 500 words."""
    user = f"Candidate profile: {profile_cv}\nPosition required profile: {profile_jd}\nSkill gaps to bridge: {gap_names}\nGraph paths: {json.dumps(paths, ensure_ascii=False)}"
    return call_claude(system, user, 1000)

def match_analysis(cv_ids, jd_ids):
    matched  = [i for i in jd_ids if i in cv_ids]
    missing  = [i for i in jd_ids if i not in cv_ids]
    bonus    = [i for i in cv_ids if i not in jd_ids]
    pct      = round(len(matched)/len(jd_ids)*100, 1) if jd_ids else 0
    return matched, missing, bonus, pct

def build_graph_data(cv_ids, jd_ids, paths):
    relevant = set(cv_ids) | set(jd_ids)
    for p in paths.values():
        for step in p["steps"]: relevant.add(step["id"])
    nodes, edges = [], []
    for sid in relevant:
        if sid not in TAXONOMY: continue
        nodes.append({"id":sid,"label":TAXONOMY[sid]["name"],"level":TAXONOMY[sid]["level"],
                      "cat":TAXONOMY[sid]["cat"],"color":CAT_COLORS.get(TAXONOMY[sid]["cat"],"#888"),
                      "owned": sid in cv_ids,"required": sid in jd_ids})
        for succ in GRAPH.successors(sid):
            if succ in relevant: edges.append({"from":sid,"to":succ})
    return {"nodes":nodes,"edges":edges}

@app.route("/")
def index(): return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    cv_file  = request.files.get("cv")
    jd_file  = request.files.get("jd")
    jd_text_input = request.form.get("jd_text","").strip()

    if not cv_file or not allowed(cv_file.filename):
        return jsonify({"error":"Please upload a valid CV (PDF or DOCX)."}), 400

    cv_bytes = cv_file.read()
    cv_text  = extract_text(cv_bytes, secure_filename(cv_file.filename))
    if len(cv_text) < 50:
        return jsonify({"error":"Could not extract text from CV. Make sure it is not a scanned image."}), 422

    # JD: file takes priority, then textarea
    jd_text = ""
    if jd_file and jd_file.filename and allowed(jd_file.filename):
        jd_bytes = jd_file.read()
        jd_text  = extract_text(jd_bytes, secure_filename(jd_file.filename))
    elif jd_text_input:
        jd_text = jd_text_input

    # --- Agents ---
    cv_result = locator(cv_text, "cv")
    cv_ids    = [s["id"] for s in cv_result.get("skills",[]) if s["id"] in TAXONOMY]

    jd_result, jd_ids = {}, []
    if jd_text:
        jd_result = locator(jd_text, "jd")
        jd_ids    = [s["id"] for s in jd_result.get("skills",[]) if s["id"] in TAXONOMY]

    connections = connector(cv_ids)

    all_reachable = {s for sid in cv_ids for s in GRAPH.successors(sid)} - set(cv_ids)
    gaps = list(all_reachable)[:6]
    if jd_ids:
        gaps = [i for i in jd_ids if i not in cv_ids][:6]

    paths = pathfinder(cv_ids, gaps)

    matched, missing, bonus, match_pct = [], [], [], None
    if jd_ids:
        matched, missing, bonus, match_pct = match_analysis(cv_ids, jd_ids)

    plan = learning_plan(
        cv_result.get("profile_summary",""),
        jd_result.get("profile_summary","") if jd_result else "Not provided",
        gaps, paths
    )

    graph_data = build_graph_data(cv_ids, jd_ids, paths)

    def enrich(ids): return [{"id":i,"name":TAXONOMY[i]["name"],"level":TAXONOMY[i]["level"],"cat":TAXONOMY[i]["cat"]} for i in ids if i in TAXONOMY]

    return jsonify({
        "cv_summary":    cv_result.get("profile_summary",""),
        "jd_summary":    jd_result.get("profile_summary","") if jd_result else "",
        "cv_skills":     cv_result.get("skills",[]),
        "jd_skills":     jd_result.get("skills",[]) if jd_result else [],
        "gaps":          enrich(gaps),
        "matched":       enrich(matched),
        "missing":       enrich(missing),
        "bonus":         enrich(bonus),
        "match_pct":     match_pct,
        "paths":         paths,
        "learning_plan": plan,
        "graph":         graph_data,
        "has_jd":        bool(jd_text),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)

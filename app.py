import json
import re
from io import BytesIO
from pathlib import Path
import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE_DIR = Path(__file__).parent
BANK_DIR = BASE_DIR / "question_bank"
REQUIRED = ["id","skills","parts","title","question","expected_answer","interviewer_memo","follow_ups","difficulty"]

def load_json_file(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        lines = raw.splitlines()
        excerpt = lines[e.lineno-1] if 0 < e.lineno <= len(lines) else ""
        pointer = " " * max(e.colno-1,0) + "^"
        raise ValueError(f"JSON invalide — ligne {e.lineno}, colonne {e.colno}: {e.msg}\n{excerpt}\n{pointer}")
    if isinstance(data, dict):
        if "questions" not in data:
            raise ValueError("Objet JSON détecté, mais la clé 'questions' est absente.")
        data = data["questions"]
    if not isinstance(data, list):
        raise ValueError("La racine doit être [...] ou {'questions': [...]} .")
    return data

def validate(q, source, n):
    errors=[]
    if not isinstance(q,dict):
        return [f"{source}: question #{n} doit être un objet."]
    for k in REQUIRED:
        if k not in q: errors.append(f"{source}: question #{n}: champ absent '{k}'.")
    if "skills" in q and not isinstance(q["skills"],list): errors.append(f"{source}: question #{n}: skills doit être une liste.")
    if "parts" in q and not isinstance(q["parts"],list): errors.append(f"{source}: question #{n}: parts doit être une liste.")
    if "difficulty" in q and not isinstance(q["difficulty"],int): errors.append(f"{source}: question #{n}: difficulty doit être un entier.")
    return errors

def load_bank():
    bank=[]; errors=[]; ids=set()
    files=sorted(BANK_DIR.glob("*.json"))
    for path in files:
        try: data=load_json_file(path)
        except ValueError as e:
            errors.append(f"{path.name}: {e}"); continue
        for n,q in enumerate(data,1):
            errs=validate(q,path.name,n)
            if errs: errors.extend(errs); continue
            if q["id"] in ids:
                errors.append(f"{path.name}: id dupliqué '{q['id']}'."); continue
            ids.add(q["id"]); q["_source_file"]=path.name; bank.append(q)
    if not files: errors.append(f"Aucun .json dans {BANK_DIR}")
    return bank,errors,files

def tok(s):
    return {x for x in re.sub(r"[^a-z0-9+#]+"," ",str(s).lower()).split() if len(x)>=2}

def score(q,ctx):
    t=tok(ctx); s=0
    for x in q.get("skills",[]): s+=4*len(tok(x.replace("."," "))&t)
    for x in q.get("parts",[]): s+=2*len(tok(x)&t)
    return s

def choose_parts(domain,role,langs,tech):
    c=f"{domain} {role} {langs} {tech}".lower(); p=[]
    def add(n,r):
        if not any(x["name"]==n for x in p): p.append({"name":n,"reason":r})
    if any(x in c for x in ["c++","cpp","python","java","rust","go"]): add("Fondamentaux techniques","Maîtrise du langage et concepts difficiles.")
    if any(x in c for x in ["iot","embedded","embarqué","device","edge"]): add("Architecture IoT","Contraintes device, réseau, edge et résilience.")
    if any(x in c for x in ["mqtt","grpc","api","backend","microservice","rest","some/ip","someip","can"]): add("Communication & protocoles","Choix de protocoles et implications.")
    if any(x in c for x in ["autosar","automotive","can","some/ip","someip","ecu","linux"]): add("Architecture métier","Contraintes et architecture du domaine.")
    if any(x in c for x in ["cloud","aws","azure","gcp","kubernetes","docker"]): add("Cloud & Production","Déploiement, observabilité et exploitation.")
    if any(x in c for x in ["security","sécurité","automotive","iot","cloud"]): add("Sécurité","Identité, permissions et menaces.")
    if any(x in c for x in ["tech lead","lead","architect","senior"]): add("Leadership & arbitrage","Décision, communication et gestion des risques.")
    add("Qualité & validation","Tests, debugging et fiabilité.")
    add("Résilience","Pannes, reprise et comportement dégradé.")
    return p[:6]

def choose(bank,domain,role,langs,tech,n):
    ctx=f"{domain} {role} {langs} {tech}"
    parts=choose_parts(domain,role,langs,tech)
    ranked=sorted(bank,key=lambda q:(score(q,ctx),q.get("difficulty",3)),reverse=True)
    out=[]; used=set()
    for p in parts:
        for q in [x for x in ranked if x["id"] not in used and p["name"] in x.get("parts",[])][:2]:
            if len(out)>=n: break
            out.append((p["name"],q)); used.add(q["id"])
    for q in ranked:
        if len(out)>=n: break
        if q["id"] not in used:
            part=next((p["name"] for p in parts if p["name"] in q.get("parts",[])),"Compléments")
            out.append((part,q)); used.add(q["id"])
    return parts,out

def md(parts,sel,langs,domain,role,tech):
    a=[f"# Entretien technique — {role}","","**Domaine :** "+domain,f"**Langages :** {langs}",f"**Technologies :** {tech}","","## Structure",""]
    a += [f"{i}. **{p['name']}** — {p['reason']}" for i,p in enumerate(parts,1)]
    a += ["","## Questions",""]
    for i,(part,q) in enumerate(sel,1):
        a += [f"## {i}. {q['title']}",f"**Partie :** {part}","","### 🎤 Question",q["question"],"","### ✅ Réponse attendue",q["expected_answer"],"","### 📝 Mémo interviewer",q["interviewer_memo"],"","### 🔎 Relances / signaux",q["follow_ups"],""]
    return "\n".join(a)

def docx(parts,sel,langs,domain,role,tech):
    d=Document(); d.styles["Normal"].font.name="Aptos"; d.styles["Normal"].font.size=Pt(10)
    h=d.add_heading(f"Entretien technique — {role}",0); h.alignment=WD_ALIGN_PARAGRAPH.CENTER
    d.add_paragraph(f"Domaine : {domain}"); d.add_paragraph(f"Langages : {langs}"); d.add_paragraph(f"Technologies : {tech}")
    d.add_heading("Structure",1)
    for i,p in enumerate(parts,1): d.add_paragraph(f"{i}. {p['name']} — {p['reason']}")
    for i,(part,q) in enumerate(sel,1):
        d.add_page_break(); d.add_heading(f"{i}. {q['title']}",1); d.add_paragraph(f"Partie : {part}")
        for lab,val in [("🎤 Question",q["question"]),("✅ Réponse attendue",q["expected_answer"]),("📝 Mémo interviewer",q["interviewer_memo"]),("🔎 Relances / signaux",q["follow_ups"])]:
            p=d.add_paragraph(); p.add_run(lab+"\n").bold=True; p.add_run(val)
    b=BytesIO(); d.save(b); b.seek(0); return b

st.set_page_config(page_title="Interview Builder Offline v3",page_icon="🎯",layout="wide")
st.title("🎯 Interview Builder — Offline v3")
st.caption("Bibliothèque multi-fichiers • validation JSON • sélection automatique • Word + Markdown")
bank,errors,files=load_bank()

with st.sidebar:
    st.header("Profil")
    langs=st.text_input("Langages / frameworks","C++")
    domain=st.text_input("Domaine","Automotive")
    role=st.text_input("Rôle","Tech Lead")
    tech=st.text_input("Technologies","AUTOSAR, CAN, SOME/IP, Linux")
    maxn=max(6,len(bank))
    n=st.slider("Nombre de questions",6,min(40,maxn),min(15,maxn))
    build=st.button("🎲 Construire l'entretien",type="primary",use_container_width=True)
    st.divider(); st.write(f"**{len(bank)} questions valides**"); st.write(f"**{len(files)} fichiers JSON**")

if errors:
    st.error(f"{len(errors)} problème(s) dans la bibliothèque.")
    with st.expander("🔎 Détails"):
        for e in errors: st.code(e)

if not bank:
    st.warning("Aucune question valide. Ajoute des fichiers JSON dans question_bank/.")
    st.stop()

if build:
    st.session_state["interview"]=choose(bank,domain,role,langs,tech,n)

if "interview" in st.session_state:
    parts,sel=st.session_state["interview"]
    st.success(f"Entretien construit : {len(parts)} parties / {len(sel)} questions")
    st.subheader("🧩 Structure")
    cols=st.columns(3)
    for i,p in enumerate(parts):
        with cols[i%3]: st.info(f"**{i+1}. {p['name']}**\n\n{p['reason']}")
    st.subheader("🎤 Questionnaire")
    for i,(part,q) in enumerate(sel,1):
        with st.expander(f"{i}. {q['title']} — {part}"):
            st.caption(f"Source : {q.get('_source_file','?')} • difficulté {q.get('difficulty','?')}/5")
            st.markdown("**Question**"); st.write(q["question"])
            st.markdown("**Réponse attendue**"); st.write(q["expected_answer"])
            st.markdown("**Mémo interviewer**"); st.write(q["interviewer_memo"])
            st.markdown("**Relances / signaux**"); st.write(q["follow_ups"])
    c1,c2=st.columns(2)
    with c1: st.download_button("📝 Markdown",md(parts,sel,langs,domain,role,tech),"entretien_technique.md","text/markdown",use_container_width=True)
    with c2: st.download_button("📄 Word",docx(parts,sel,langs,domain,role,tech),"entretien_technique.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)

with st.expander("📚 Formats JSON acceptés"):
    st.markdown("""**Format A**
```json
{"questions":[{"id":"...","skills":[],"parts":[],"title":"...","question":"...","expected_answer":"...","interviewer_memo":"...","follow_ups":"...","difficulty":3}]}
```
**Format B**
```json
[{"id":"...","skills":[],"parts":[],"title":"...","question":"...","expected_answer":"...","interviewer_memo":"...","follow_ups":"...","difficulty":3}]
```
Tous les `.json` de `question_bank/` sont chargés automatiquement. Un JSON invalide affiche le fichier, la ligne, la colonne et un extrait au lieu de faire planter l'application.
""")

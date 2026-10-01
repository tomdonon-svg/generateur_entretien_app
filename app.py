import json, io, re
from pathlib import Path
import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

BANK_FILE=Path(__file__).parent/"question_bank.json"

@st.cache_data
def load_bank():
    return json.loads(BANK_FILE.read_text(encoding="utf-8"))["questions"]

def norm(s):
    return re.sub(r"[^a-z0-9+#]+"," ",s.lower()).strip()

def score(q, text):
    t=norm(text)
    return sum(3 for tag in q["tags"] if norm(tag) and norm(tag) in t)

def select_questions(languages,domain,role,technologies,count):
    bank=load_bank()
    context=f"{languages} {domain} {role} {technologies}"
    ranked=sorted(bank,key=lambda q:score(q,context),reverse=True)
    selected=[]; topics=set()
    # First pass: diversify
    for q in ranked:
        if len(selected)>=count: break
        if not any(x in topics for x in q["topics"]) or len(selected)>=max(6,count//2):
            selected.append(q); topics.update(q["topics"])
    for q in ranked:
        if len(selected)>=count: break
        if q not in selected: selected.append(q)
    return selected

def md(selected,lang,domain,role,tech):
    out=[f"# Entretien technique — {role}","","**Domaine :** "+domain,
         f"**Langages :** {lang or 'Non précisé'}",
         f"**Technologies :** {tech or 'Non précisé'}","","## Questions",""]
    for i,q in enumerate(selected,1):
        out += [f"# {i}. {q['title']}","","### 🎤 Question à poser","",
                "> "+q["question"],"","### ✅ Réponse attendue","",q["expected_answer"],
                "","### 📝 Mémo interviewer","",q["interviewer_memo"],
                "","### 🔎 Relances / signaux","",q["follow_ups_and_signals"],""]
    return "\n".join(out)

def docx(selected,lang,domain,role,tech):
    d=Document(); d.styles["Normal"].font.name="Aptos"; d.styles["Normal"].font.size=Pt(10)
    p=d.add_heading(f"Entretien technique — {role}",0); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    d.add_paragraph(f"Domaine : {domain}"); d.add_paragraph(f"Langages : {lang or 'Non précisé'}")
    d.add_paragraph(f"Technologies : {tech or 'Non précisé'}")
    for i,q in enumerate(selected,1):
        d.add_page_break(); d.add_heading(f"{i}. {q['title']}",1)
        for label,value in [("🎤 Question à poser",q["question"]),("✅ Réponse attendue",q["expected_answer"]),
                           ("📝 Mémo interviewer",q["interviewer_memo"]),("🔎 Relances / signaux",q["follow_ups_and_signals"])]:
            p=d.add_paragraph(); p.add_run(label+"\n").bold=True; p.add_run(value)
    b=io.BytesIO(); d.save(b); b.seek(0); return b

st.set_page_config(page_title="Interview Builder Offline",page_icon="🎯",layout="wide")
st.title("🎯 Interview Builder — Offline")
st.caption("Aucune API OpenAI. La sélection est faite localement dans la bibliothèque.")
bank=load_bank()

with st.sidebar:
    st.header("Configuration")
    lang=st.text_input("Langages / frameworks","C++")
    domain=st.text_input("Domaine","IoT")
    role=st.text_input("Rôle","Tech Lead")
    tech=st.text_input("Technologies","MQTT, gRPC, AWS")
    count=st.slider("Nombre de questions",6,min(40,len(bank)),min(15,len(bank)))
    generate=st.button("🎲 Construire l'entretien",type="primary",use_container_width=True)
    st.divider(); st.write(f"**{len(bank)} questions** dans la bibliothèque")

if generate:
    st.session_state["selected"]=select_questions(lang,domain,role,tech,count)
    st.session_state["config"]=(lang,domain,role,tech)

if "selected" in st.session_state:
    selected=st.session_state["selected"]; lang,domain,role,tech=st.session_state["config"]
    st.success(f"{len(selected)} questions sélectionnées pour {role} / {domain}")
    for i,q in enumerate(selected,1):
        with st.expander(f"{i}. {q['title']} — {', '.join(q['topics'])}"):
            st.markdown("**🎤 Question à poser**"); st.write(q["question"])
            st.markdown("**✅ Réponse attendue**"); st.write(q["expected_answer"])
            st.markdown("**📝 Mémo interviewer**"); st.write(q["interviewer_memo"])
            st.markdown("**🔎 Relances / signaux**"); st.write(q["follow_ups_and_signals"])
    c1,c2=st.columns(2)
    with c1: st.download_button("📝 Télécharger Markdown",md(selected,lang,domain,role,tech),"entretien_technique.md","text/markdown",use_container_width=True)
    with c2: st.download_button("📄 Télécharger Word",docx(selected,lang,domain,role,tech),"entretien_technique.docx","application/vnd.openxmlformats-officedocument.wordprocessingml.document",use_container_width=True)

st.divider()
st.caption("Pour enrichir la bibliothèque, ajoute des objets au fichier question_bank.json.")

import os
import re
from pathlib import Path

import streamlit as st
from openai import OpenAI
from pydantic import BaseModel
from typing import List
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


# =========================
# Structured output models
# =========================

class Question(BaseModel):
    title: str
    question: str
    expected_answer: str
    interviewer_memo: str
    follow_ups_and_signals: str


class Section(BaseModel):
    title: str
    objective: str
    estimated_minutes: int
    questions: List[Question]


class EvaluationCriterion(BaseModel):
    name: str
    description: str


class InterviewGuide(BaseModel):
    title: str
    subtitle: str
    duration_minutes: int
    recommended_duration_minutes: int
    sections: List[Section]
    scoring_scale: str
    score_interpretation: List[str]
    key_decision_points: List[str]
    evaluation_criteria: List[EvaluationCriterion]


SYSTEM_PROMPT = """
Tu es un expert en recrutement technique et en conduite d'entretiens
d'ingénieurs logiciels.

Construis une fiche d'entretien technique ORAL destinée à l'interviewer.

Le questionnaire doit être suffisamment détaillé pour que l'interviewer
puisse conduire l'entretien sans réviser les sujets auparavant.

IMPORTANT : il doit comporter EXACTEMENT 6 PARTIES.

Les 6 parties doivent être choisies dynamiquement selon :
- les langages/frameworks ;
- le domaine métier/technique ;
- le rôle ;
- les technologies ;
- le contexte.

Ne réutilise pas systématiquement une structure fixe.
Un entretien C++/IoT doit pouvoir avoir une structure différente d'un
entretien React/Frontend ou Java/Backend.

Pour CHAQUE question, produis exactement quatre éléments :

1. question
   Formulation naturelle à poser oralement.

2. expected_answer
   Éléments attendus dans une bonne réponse, avec détails techniques.

3. interviewer_memo
   Mémo détaillé pour l'interviewer : concepts, terminologie, architecture,
   exemples, pièges, compromis et points permettant de juger la réponse.

4. follow_ups_and_signals
   Relances, bons signaux, signaux faibles et erreurs fréquentes.

PRINCIPES :
- Oral, pas un examen écrit.
- Favoriser le raisonnement plutôt que la récitation.
- Mélanger concepts, scénarios, architecture, debugging, production et
  arbitrages.
- Les technologies données sont des indications, pas des obligations.
- Adapter la profondeur au niveau du poste.
- Pour Tech Lead : architecture, arbitrage, leadership technique,
  communication et prise de décision.
- Pour Senior : profondeur technique, conception et résolution de problèmes.
- Ne pas inventer de contraintes absentes du contexte.

DURÉE :
Respecte autant que possible la durée et le nombre de questions demandés.
Une légère variation est acceptable si elle améliore la qualité.

ÉVALUATION :
Fournis une grille permettant de distinguer une maîtrise faible, correcte,
senior et excellente pour le niveau demandé.

Le questionnaire doit permettre de différencier un candidat qui connaît des
définitions d'un candidat qui comprend réellement pourquoi, quand et comment
utiliser une technologie, ainsi que ses limites.
"""


def build_prompt(languages, domain, role, technologies, duration, questions, context):
    return f"""
Construis un entretien technique avec :

LANGAGES / FRAMEWORKS :
{languages or "Non précisé"}

DOMAINE :
{domain}

RÔLE :
{role}

TECHNOLOGIES :
{technologies or "Non précisé"}

DURÉE CIBLE :
{duration} minutes

NOMBRE DE QUESTIONS CIBLE :
{questions}

CONTEXTE :
{context or "Aucun contexte supplémentaire."}

Choisis EXACTEMENT 6 parties pertinentes.
Répartis intelligemment les questions.
Chaque partie doit avoir un objectif clair.
"""


def generate_markdown(guide):
    lines = [
        f"# {guide.title}", "",
        f"**{guide.subtitle}**", "",
        f"**Durée cible :** {guide.duration_minutes} min  ",
        f"**Durée recommandée :** {guide.recommended_duration_minutes} min",
        "",
        "## Structure", "",
        "| Partie | Sujet | Objectif | Temps | Questions |",
        "|---|---|---|---:|---:|",
    ]

    for i, section in enumerate(guide.sections, 1):
        lines.append(
            f"| {i} | {section.title} | {section.objective} | "
            f"{section.estimated_minutes} min | {len(section.questions)} |"
        )

    for i, section in enumerate(guide.sections, 1):
        lines += [
            "", f"# {i}. {section.title}", "",
            f"**Objectif :** {section.objective}", "",
            f"**Temps indicatif :** {section.estimated_minutes} min",
        ]

        for j, q in enumerate(section.questions, 1):
            lines += [
                "", f"## Q{j} — {q.title}", "",
                "### 🎤 Question à poser", "", f"> {q.question}", "",
                "### ✅ Réponse attendue", "", q.expected_answer, "",
                "### 📝 Mémo interviewer", "", q.interviewer_memo, "",
                "### 🔎 Relances / signaux", "", q.follow_ups_and_signals,
            ]

    lines += [
        "", "# Grille d'évaluation", "",
        f"**Échelle :** {guide.scoring_scale}", "",
        "## Interprétation", "",
    ]
    lines += [f"- {x}" for x in guide.score_interpretation]

    lines += ["", "## Critères d'évaluation", "",
              "| Critère | Description |", "|---|---|"]
    lines += [f"| {x.name} | {x.description} |" for x in guide.evaluation_criteria]

    lines += ["", "## Points de décision importants", ""]
    lines += [f"- {x}" for x in guide.key_decision_points]

    return "\n".join(lines) + "\n"


def generate_docx(guide):
    path = Path("/tmp/interview_guide.docx")
    doc = Document()
    doc.styles["Normal"].font.name = "Aptos"
    doc.styles["Normal"].font.size = Pt(10)

    title = doc.add_heading(guide.title, 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(guide.subtitle).italic = True

    doc.add_paragraph(f"Durée cible : {guide.duration_minutes} min")
    doc.add_paragraph(
        f"Durée recommandée : {guide.recommended_duration_minutes} min"
    )

    doc.add_heading("Structure", level=1)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for c, t in zip(table.rows[0].cells,
                    ["Partie", "Sujet", "Objectif", "Temps", "Questions"]):
        c.text = t

    for i, s in enumerate(guide.sections, 1):
        cells = table.add_row().cells
        cells[0].text = str(i)
        cells[1].text = s.title
        cells[2].text = s.objective
        cells[3].text = f"{s.estimated_minutes} min"
        cells[4].text = str(len(s.questions))

    for i, s in enumerate(guide.sections, 1):
        doc.add_page_break()
        doc.add_heading(f"{i}. {s.title}", level=1)
        doc.add_paragraph(f"Objectif : {s.objective}")
        doc.add_paragraph(f"Temps indicatif : {s.estimated_minutes} min")

        for j, q in enumerate(s.questions, 1):
            doc.add_heading(f"Q{j} — {q.title}", level=2)
            for label, text in [
                ("🎤 Question à poser", q.question),
                ("✅ Réponse attendue", q.expected_answer),
                ("📝 Mémo interviewer", q.interviewer_memo),
                ("🔎 Relances / signaux", q.follow_ups_and_signals),
            ]:
                p = doc.add_paragraph()
                p.add_run(label + "\n").bold = True
                p.add_run(text)

    doc.add_page_break()
    doc.add_heading("Grille d'évaluation", level=1)
    doc.add_paragraph(f"Échelle : {guide.scoring_scale}")

    doc.add_heading("Interprétation", level=2)
    for x in guide.score_interpretation:
        doc.add_paragraph(x, style="List Bullet")

    doc.add_heading("Critères d'évaluation", level=2)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    table.rows[0].cells[0].text = "Critère"
    table.rows[0].cells[1].text = "Description"
    for x in guide.evaluation_criteria:
        cells = table.add_row().cells
        cells[0].text = x.name
        cells[1].text = x.description

    doc.add_heading("Points de décision importants", level=2)
    for x in guide.key_decision_points:
        doc.add_paragraph(x, style="List Bullet")

    doc.save(path)
    return path


# =========================
# UI
# =========================

st.set_page_config(
    page_title="Générateur d'entretien technique",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 Générateur d'entretien technique")
st.caption(
    "Crée automatiquement une fiche d'entretien oral adaptée au poste. "
    "Les 6 parties sont choisies dynamiquement par le modèle."
)

with st.sidebar:
    st.header("Paramètres")

    api_key = st.text_input(
        "Clé API OpenAI",
        type="password",
        help="La clé n'est pas enregistrée par cette application."
    )

    languages = st.text_input(
        "Langages / frameworks",
        placeholder="C++, Python"
    )

    domain = st.text_input(
        "Domaine",
        placeholder="IoT, Backend, Frontend, Embedded..."
    )

    role = st.text_input(
        "Rôle",
        value="Tech Lead"
    )

    technologies = st.text_input(
        "Technologies",
        placeholder="MQTT, gRPC, AWS"
    )

    duration = st.slider(
        "Durée cible (minutes)",
        min_value=15,
        max_value=120,
        value=40,
        step=5,
    )

    question_count = st.slider(
        "Nombre de questions",
        min_value=6,
        max_value=40,
        value=15,
    )

    context = st.text_area(
        "Contexte complémentaire",
        placeholder=(
            "Ex. application industrielle sur Raspberry Pi, "
            "réseau instable, forte disponibilité..."
        ),
        height=120,
    )

    model = st.text_input(
        "Modèle OpenAI",
        value="gpt-5.6-luna",
    )

    generate = st.button(
        "🚀 Générer l'entretien",
        type="primary",
        use_container_width=True,
    )

if generate:
    if not api_key.strip():
        st.error("Renseigne une clé API OpenAI.")
        st.stop()

    if not domain.strip():
        st.error("Renseigne au minimum le domaine.")
        st.stop()

    with st.spinner("Génération de l'entretien en cours..."):
        try:
            client = OpenAI(api_key=api_key.strip())

            prompt = build_prompt(
                languages,
                domain,
                role,
                technologies,
                duration,
                question_count,
                context,
            )

            response = client.responses.parse(
                model=model.strip(),
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                text_format=InterviewGuide,
            )

            guide = response.output_parsed

            if guide is None:
                raise RuntimeError("Le modèle n'a retourné aucun résultat.")

            md = generate_markdown(guide)
            docx_path = generate_docx(guide)

            st.success(
                f"Entretien généré : {len(guide.sections)} parties, "
                f"{sum(len(s.questions) for s in guide.sections)} questions, "
                f"{guide.recommended_duration_minutes} min recommandées."
            )

            st.subheader("Structure générée")

            for i, section in enumerate(guide.sections, 1):
                with st.expander(
                    f"{i}. {section.title} — {section.estimated_minutes} min"
                ):
                    st.write(section.objective)
                    st.write(
                        f"**Questions :** {len(section.questions)}"
                    )

            st.subheader("Téléchargement")

            safe_name = re.sub(
                r"[^a-zA-Z0-9_-]+",
                "_",
                f"entretien_{role}_{domain}"
            ).strip("_").lower()

            st.download_button(
                "📝 Télécharger le Markdown",
                data=md,
                file_name=f"{safe_name}.md",
                mime="text/markdown",
            )

            with open(docx_path, "rb") as f:
                st.download_button(
                    "📄 Télécharger le Word",
                    data=f.read(),
                    file_name=f"{safe_name}.docx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                )

            st.subheader("Aperçu")

            for i, section in enumerate(guide.sections, 1):
                st.markdown(f"## {i}. {section.title}")
                st.caption(
                    f"{section.objective} — "
                    f"{section.estimated_minutes} min"
                )

                for j, q in enumerate(section.questions, 1):
                    with st.expander(f"Q{j} — {q.title}"):
                        st.markdown("**🎤 Question à poser**")
                        st.write(q.question)

                        st.markdown("**✅ Réponse attendue**")
                        st.write(q.expected_answer)

                        st.markdown("**📝 Mémo interviewer**")
                        st.write(q.interviewer_memo)

                        st.markdown("**🔎 Relances / signaux**")
                        st.write(q.follow_ups_and_signals)

            st.markdown("---")
            st.subheader("Grille d'évaluation")

            st.write(f"**Échelle :** {guide.scoring_scale}")

            for x in guide.score_interpretation:
                st.markdown(f"- {x}")

            st.markdown("### Critères")
            for x in guide.evaluation_criteria:
                st.markdown(f"**{x.name}** — {x.description}")

            st.markdown("### Points de décision importants")
            for x in guide.key_decision_points:
                st.markdown(f"- {x}")

        except Exception as exc:
            st.error("La génération a échoué.")
            st.exception(exc)


st.markdown("---")
st.caption(
    "Les fichiers sont générés dans la session de l'application. "
    "La clé API saisie dans l'interface n'est pas stockée par ce code."
)

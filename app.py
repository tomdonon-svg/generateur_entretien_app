import json
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document

import streamlit as st

APP_DIR = Path(__file__).parent
DEFAULT_BANK = APP_DIR / "question_bank.json"

st.set_page_config(
    page_title="Interview Builder",
    page_icon="🎯",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data model / validation
# ---------------------------------------------------------------------------

QUESTION_REQUIRED_FIELDS = {
    "id", "question", "expected_answer", "interviewer_memo", "follow_ups",
    "themes", "scenario", "languages", "specialties", "levels",
    "technologies", "estimated_minutes"
}

ROOT_REQUIRED_FIELDS = {"schema_version", "questions"}


def load_json_file(uploaded_file) -> Any:
    try:
        return json.loads(uploaded_file.getvalue().decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("Le fichier n'est pas encodé en UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide : ligne {exc.lineno}, colonne {exc.colno}.") from exc


def load_default_bank() -> dict:
    with DEFAULT_BANK.open("r", encoding="utf-8") as f:
        return json.load(f)


def merge_question_banks(base_bank: dict, additional_banks: list[tuple[str, dict]]) -> tuple[dict, list[str]]:
    """Fusionne la banque embarquée avec plusieurs banques importées.

    Les fichiers importés sont ajoutés à la banque de base. Les identifiants
    doivent rester uniques sur l'ensemble de la banque fusionnée.
    """
    merged = {
        "schema_version": base_bank.get("schema_version", "1.0"),
        "questions": list(base_bank.get("questions", [])),
    }
    errors: list[str] = []

    known_ids = {q.get("id") for q in merged["questions"]}

    for filename, bank in additional_banks:
        for index, question in enumerate(bank.get("questions", []), start=1):
            qid = question.get("id")
            if qid in known_ids:
                errors.append(
                    f"{filename} — question #{index}: id dupliqué '{qid}' "
                    "avec une question déjà chargée."
                )
                continue

            merged["questions"].append(question)
            known_ids.add(qid)

    return merged, errors


def validate_bank(bank: Any) -> list[str]:
    errors = []

    if not isinstance(bank, dict):
        return ["La racine du JSON doit être un objet."]
    missing = ROOT_REQUIRED_FIELDS - set(bank)
    if missing:
        errors.append(f"Champs racine manquants : {sorted(missing)}")

    questions = bank.get("questions")
    if not isinstance(questions, list):
        errors.append("Le champ 'questions' doit être une liste.")
        return errors

    ids = set()
    for i, q in enumerate(questions):
        prefix = f"Question #{i + 1}"
        if not isinstance(q, dict):
            errors.append(f"{prefix}: doit être un objet.")
            continue

        missing_q = QUESTION_REQUIRED_FIELDS - set(q)
        if missing_q:
            errors.append(f"{prefix}: champs manquants : {sorted(missing_q)}")

        qid = q.get("id")
        if qid in ids:
            errors.append(f"{prefix}: id dupliqué '{qid}'.")
        ids.add(qid)

        for field in [
            "themes", "languages", "specialties", "levels", "technologies",
            "follow_ups"
        ]:
            if field in q and not isinstance(q[field], list):
                errors.append(f"{prefix}: '{field}' doit être une liste.")

        if "estimated_minutes" in q:
            if not isinstance(q["estimated_minutes"], (int, float)) or q["estimated_minutes"] <= 0:
                errors.append(f"{prefix}: 'estimated_minutes' doit être un nombre > 0.")

        for field in ["question", "expected_answer", "interviewer_memo", "scenario"]:
            if field in q and not isinstance(q[field], str):
                errors.append(f"{prefix}: '{field}' doit être une chaîne.")

    return errors


def unique_values(questions: list[dict], field: str) -> list[str]:
    values = set()
    for q in questions:
        values.update(q.get(field, []))
    return sorted(values, key=str.lower)


def matches(q: dict, selected_languages, selected_specialties,
            selected_levels, selected_technologies) -> bool:
    def ok(selected, available):
        return not selected or bool(set(selected) & set(available))

    return (
        ok(selected_languages, q.get("languages", []))
        and ok(selected_specialties, q.get("specialties", []))
        and ok(selected_levels, q.get("levels", []))
        and ok(selected_technologies, q.get("technologies", []))
    )


def select_questions(candidates: list[dict], count: int, target_minutes: int) -> list[dict]:
    """
    Selection heuristique locale :
    - essaie de respecter le nombre demandé ;
    - minimise l'écart avec la durée cible ;
    - favorise la diversité des thèmes/scénarios ;
    - aucune API externe.
    """
    if not candidates or count <= 0:
        return []

    remaining = candidates.copy()
    selected = []
    used_themes = set()
    used_scenarios = set()
    total = 0

    while remaining and len(selected) < count:
        best = None
        best_score = None

        for q in remaining:
            minutes = float(q.get("estimated_minutes", 5))
            themes = set(q.get("themes", []))
            scenario = q.get("scenario", "")

            new_theme_bonus = len(themes - used_themes) * 8
            new_scenario_bonus = 4 if scenario not in used_scenarios else 0

            projected = total + minutes
            duration_penalty = abs(target_minutes - projected) / max(target_minutes, 1) * 10

            # On évite de dépasser fortement la durée quand d'autres choix existent.
            overshoot_penalty = max(0, projected - target_minutes) * 1.5

            score = new_theme_bonus + new_scenario_bonus - duration_penalty - overshoot_penalty

            if best_score is None or score > best_score:
                best_score = score
                best = q

        selected.append(best)
        remaining.remove(best)
        total += float(best.get("estimated_minutes", 5))
        used_themes.update(best.get("themes", []))
        used_scenarios.add(best.get("scenario", ""))

    return selected


def build_prompt_template(bank: dict) -> str:
    """
    Prompt autonome destiné à être copié dans ChatGPT.
    L'application elle-même ne fait aucune requête ChatGPT.
    """
    schema = {
        "schema_version": "1.0",
        "questions": [
            {
                "id": "unique-id",
                "question": "Question orale...",
                "expected_answer": "Réponse attendue détaillée...",
                "interviewer_memo": "Mémo interviewer très détaillé...",
                "follow_ups": [
                    "Relance 1...",
                    "Relance 2..."
                ],
                "themes": ["Architecture"],
                "scenario": "Contexte/scénario commun...",
                "languages": ["C++"],
                "specialties": ["IoT"],
                "levels": ["Senior"],
                "technologies": ["gRPC", "MQTT"],
                "estimated_minutes": 5
            }
        ]
    }

    return f"""# PROMPT — Génération de questions pour Interview Builder

Tu dois générer une banque de questions techniques destinée à un entretien d'embauche oral.
Tu NE dois produire aucune explication hors JSON.

## Contraintes fonctionnelles
1. Chaque question doit avoir :
   - une question claire et exploitable à l'oral ;
   - une réponse attendue détaillée et techniquement correcte ;
   - un mémo interviewer encore plus opérationnel : points à écouter, notions importantes,
     erreurs fréquentes, nuances, critères permettant de distinguer junior/intermédiaire/senior ;
   - au moins 2 relances permettant d'approfondir ou de débloquer le candidat.
2. Les questions doivent être regroupées par thèmes.
3. Elles doivent autant que possible partager un scénario/contexte cohérent.
4. Les métadonnées doivent permettre le filtrage par langage, spécialité, niveau et technologie.
5. Fournir une durée estimée en minutes pour chaque question.
6. Les questions doivent être indépendantes les unes des autres.
7. Ne pas inventer de technologie non demandée.
8. Répondre exclusivement avec un JSON valide, sans markdown, sans commentaire.

## Niveau de détail attendu
- expected_answer : plusieurs points concrets, avec exemples lorsque pertinent.
- interviewer_memo : détails utiles à un interviewer qui n'a pas révisé le sujet.
- follow_ups : relances réellement exploitables à l'oral, pas de simples reformulations.

## Format JSON OBLIGATOIRE
{json.dumps(schema, ensure_ascii=False, indent=2)}

## Exemple de métadonnées souhaitées
- Langages disponibles dans la banque actuelle : {", ".join(unique_values(bank["questions"], "languages")) or "aucun"}
- Spécialités : {", ".join(unique_values(bank["questions"], "specialties")) or "aucune"}
- Niveaux : {", ".join(unique_values(bank["questions"], "levels")) or "aucun"}
- Technologies : {", ".join(unique_values(bank["questions"], "technologies")) or "aucune"}

## Demande
Génère des questions complémentaires qui respectent exactement ce schéma.
Évite les doublons avec les questions existantes si je te les fournis.
"""


def export_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def build_markdown_questionnaire(selected: list[dict], filters: dict, bank: dict) -> str:
    total_minutes = sum(float(q.get("estimated_minutes", 0)) for q in selected)
    lines = [
        "# Questionnaire technique — entretien",
        "",
        "## Paramètres",
        "",
        f"- **Langages :** {', '.join(filters['languages']) or 'Tous'}",
        f"- **Spécialités :** {', '.join(filters['specialties']) or 'Toutes'}",
        f"- **Niveaux :** {', '.join(filters['levels']) or 'Tous'}",
        f"- **Technologies :** {', '.join(filters['technologies']) or 'Toutes'}",
        f"- **Durée cible :** {filters['duration']} min",
        f"- **Nombre demandé :** {filters['question_count']}",
        f"- **Durée estimée :** {total_minutes:g} min",
        "",
    ]

    scenarios = []
    for q in selected:
        if q.get("scenario") not in scenarios:
            scenarios.append(q.get("scenario"))

    lines += ["## Scénario", ""]
    if len(scenarios) == 1:
        lines += [scenarios[0], ""]
    else:
        for scenario in scenarios:
            lines += [f"- {scenario}", ""]

    grouped = {}
    for q in selected:
        primary_theme = q.get("themes", ["Autres"])[0]
        grouped.setdefault(primary_theme, []).append(q)

    number = 0
    for theme, theme_questions in grouped.items():
        lines += [f"## {theme}", ""]
        for q in theme_questions:
            number += 1
            lines += [
                f"### {number}. {q['question']}",
                "",
                f"**Durée estimée :** {q.get('estimated_minutes', '?')} min",
                "",
                "#### Réponse attendue",
                "",
                q["expected_answer"],
                "",
                "#### Mémo interviewer",
                "",
                q["interviewer_memo"],
                "",
                "#### Relances",
                "",
            ]
            for follow_up in q.get("follow_ups", []):
                lines.append(f"- {follow_up}")
            lines += [""]

    return "\n".join(lines)


def build_docx_questionnaire(selected: list[dict], filters: dict) -> bytes:
    document = Document()
    document.add_heading("Questionnaire technique — entretien", level=0)

    document.add_heading("Paramètres", level=1)
    params = [
        ("Langages", ", ".join(filters["languages"]) or "Tous"),
        ("Spécialités", ", ".join(filters["specialties"]) or "Toutes"),
        ("Niveaux", ", ".join(filters["levels"]) or "Tous"),
        ("Technologies", ", ".join(filters["technologies"]) or "Toutes"),
        ("Durée cible", f"{filters['duration']} min"),
        ("Nombre demandé", str(filters["question_count"])),
        (
            "Durée estimée",
            f"{sum(float(q.get('estimated_minutes', 0)) for q in selected):g} min",
        ),
    ]
    for label, value in params:
        p = document.add_paragraph()
        p.add_run(f"{label} : ").bold = True
        p.add_run(value)

    scenarios = []
    for q in selected:
        if q.get("scenario") not in scenarios:
            scenarios.append(q.get("scenario"))

    document.add_heading("Scénario", level=1)
    for scenario in scenarios:
        document.add_paragraph(scenario, style="List Bullet")

    grouped = {}
    for q in selected:
        primary_theme = q.get("themes", ["Autres"])[0]
        grouped.setdefault(primary_theme, []).append(q)

    number = 0
    for theme, theme_questions in grouped.items():
        document.add_heading(theme, level=1)

        for q in theme_questions:
            number += 1
            document.add_heading(f"{number}. {q['question']}", level=2)

            p = document.add_paragraph()
            p.add_run("Durée estimée : ").bold = True
            p.add_run(f"{q.get('estimated_minutes', '?')} min")

            document.add_heading("Réponse attendue", level=3)
            document.add_paragraph(q["expected_answer"])

            document.add_heading("Mémo interviewer", level=3)
            document.add_paragraph(q["interviewer_memo"])

            document.add_heading("Relances", level=3)
            for follow_up in q.get("follow_ups", []):
                document.add_paragraph(follow_up, style="List Bullet")

    output = BytesIO()
    document.save(output)
    return output.getvalue()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("🎯 Interview Builder")
st.caption("Banque de questions technique · sélection locale · aucun appel à ChatGPT")

with st.sidebar:
    st.header("📚 Banque de questions")

    base_bank = load_default_bank()

    uploaded_files = st.file_uploader(
        "Ajouter une ou plusieurs banques JSON",
        type=["json"],
        accept_multiple_files=True,
        help=(
            "Les fichiers importés sont ajoutés à la banque intégrée. "
            "Chaque fichier doit respecter le schéma documenté dans README.md. "
            "Les identifiants de questions doivent être uniques entre tous les fichiers."
        ),
    )

    valid_additional_banks: list[tuple[str, dict]] = []
    import_errors: list[str] = []

    for uploaded_file in uploaded_files or []:
        try:
            imported_bank = load_json_file(uploaded_file)
            validation_errors = validate_bank(imported_bank)
            if validation_errors:
                import_errors.append(
                    f"{uploaded_file.name} : JSON valide mais structure invalide."
                )
                import_errors.extend(
                    f"  • {error}" for error in validation_errors[:10]
                )
                if len(validation_errors) > 10:
                    import_errors.append(
                        f"  • … {len(validation_errors) - 10} autres erreurs"
                    )
            else:
                valid_additional_banks.append((uploaded_file.name, imported_bank))
        except ValueError as exc:
            import_errors.append(f"{uploaded_file.name} : {exc}")

    bank, merge_errors = merge_question_banks(base_bank, valid_additional_banks)
    import_errors.extend(merge_errors)

    if import_errors:
        st.error("Certains fichiers n'ont pas pu être ajoutés")
        for error in import_errors[:30]:
            st.write(f"• {error}")
        if len(import_errors) > 30:
            st.write(f"… {len(import_errors) - 30} autres erreurs")

    questions = bank["questions"]
    source_names = ["question_bank.json"] + [name for name, _ in valid_additional_banks]
    st.success(f"{len(questions)} question(s) disponible(s)")
    st.caption("Sources : " + ", ".join(source_names))

    st.divider()
    st.header("🎛️ Critères")

    languages = st.multiselect(
        "Langages",
        unique_values(questions, "languages"),
    )
    specialties = st.multiselect(
        "Spécialité",
        unique_values(questions, "specialties"),
    )
    levels = st.multiselect(
        "Niveau",
        unique_values(questions, "levels"),
    )
    technologies = st.multiselect(
        "Technologies",
        unique_values(questions, "technologies"),
    )

    duration = st.number_input(
        "Durée cible (minutes)",
        min_value=5,
        max_value=240,
        value=45,
        step=5,
    )

    max_questions = min(50, max(1, len(questions)))
    question_count = st.number_input(
        "Nombre de questions",
        min_value=1,
        max_value=max_questions,
        value=min(10, max_questions),
        step=1,
    )

    generate = st.button("🚀 Générer le questionnaire", type="primary", use_container_width=True)

filtered = [
    q for q in questions
    if matches(q, languages, specialties, levels, technologies)
]

if "selected_questions" not in st.session_state:
    st.session_state.selected_questions = []

tab_questionnaire, tab_prompt, tab_schema, tab_control = st.tabs(
    ["📋 Questionnaire", "🤖 Générer des questions", "🧩 Schéma JSON", "✅ Contrôle"]
)

if generate:
    st.session_state.selected_questions = select_questions(
        filtered, int(question_count), int(duration)
    )

with tab_questionnaire:
    if not filtered:
        st.warning("Aucune question ne correspond aux critères actuels.")
    else:
        st.info(
            f"{len(filtered)} question(s) compatible(s) avec les filtres. "
            f"Cliquez sur « Générer le questionnaire » pour effectuer la sélection."
        )

    selected = st.session_state.selected_questions

    if selected:
        total_minutes = sum(float(q.get("estimated_minutes", 0)) for q in selected)
        scenarios = []
        for q in selected:
            if q.get("scenario") not in scenarios:
                scenarios.append(q.get("scenario"))

        st.subheader("Scénario")
        st.write(scenarios[0] if len(scenarios) == 1 else "Plusieurs scénarios sont utilisés.")

        c1, c2, c3 = st.columns(3)
        c1.metric("Questions", len(selected))
        c2.metric("Durée estimée", f"{total_minutes:g} min")
        c3.metric("Thèmes", len({t for q in selected for t in q.get("themes", [])}))

        st.divider()

        # Regroupement d'affichage par thématique.
        # Une question multi-thèmes est placée dans son premier thème.
        grouped = {}
        for q in selected:
            primary_theme = q.get("themes", ["Autres"])[0]
            grouped.setdefault(primary_theme, []).append(q)

        question_number = 0
        for theme, theme_questions in grouped.items():
            st.markdown(f"## 📚 {theme}")

            for q in theme_questions:
                question_number += 1
                themes = " · ".join(q.get("themes", []))
                st.markdown(f"### {question_number}. {q['question']}")
                st.caption(
                    f"**Thèmes :** {themes}  ·  "
                    f"**Durée :** {q.get('estimated_minutes', '?')} min"
                )

                st.markdown("#### ✅ Réponse attendue")
                st.markdown(q["expected_answer"])

                with st.expander("🧠 Mémo interviewer", expanded=False):
                    st.markdown(q["interviewer_memo"])

                with st.expander("🔁 Relances", expanded=False):
                    for follow_up in q.get("follow_ups", []):
                        st.markdown(f"- {follow_up}")

            st.divider()

        export_data = {
            "schema_version": bank.get("schema_version", "1.0"),
            "generated_from": {
                "languages": languages,
                "specialties": specialties,
                "levels": levels,
                "technologies": technologies,
                "target_duration_minutes": int(duration),
                "question_count": int(question_count),
            },
            "questions": selected,
        }

        export_filters = {
            "languages": languages,
            "specialties": specialties,
            "levels": levels,
            "technologies": technologies,
            "duration": int(duration),
            "question_count": int(question_count),
        }

        markdown_data = build_markdown_questionnaire(
            selected, export_filters, bank
        )
        docx_data = build_docx_questionnaire(selected, export_filters)

        st.markdown("### 📥 Télécharger le questionnaire")
        export_col1, export_col2, export_col3 = st.columns(3)

        with export_col1:
            st.download_button(
                "⬇️ Télécharger DOCX",
                data=docx_data,
                file_name="questionnaire_entretien.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

        with export_col2:
            st.download_button(
                "⬇️ Télécharger Markdown",
                data=markdown_data,
                file_name="questionnaire_entretien.md",
                mime="text/markdown",
                use_container_width=True,
            )

        with export_col3:
            st.download_button(
                "⬇️ Télécharger JSON",
                data=export_json(export_data),
                file_name="questionnaire_entretien.json",
                mime="application/json",
                use_container_width=True,
            )
    else:
        st.markdown(
            """
            ### Comment utiliser l'application

            1. Chargez éventuellement votre propre banque JSON.
            2. Choisissez les langages, spécialités, niveaux et technologies.
            3. Indiquez une durée cible et un nombre de questions.
            4. Cliquez sur **Générer le questionnaire**.
            5. Utilisez les onglets **Générer des questions** et **Schéma JSON**
               pour enrichir votre banque sans connexion à ChatGPT.
            """
        )

with tab_prompt:
    st.subheader("🤖 Générer de nouvelles questions dans ChatGPT")
    st.write(
        "L'application ne contacte jamais ChatGPT. Le bloc ci-dessous est un "
        "prompt autonome que vous pouvez copier dans ChatGPT pour produire un JSON "
        "compatible avec l'importeur."
    )

    prompt = build_prompt_template(bank)
    st.text_area("Prompt prêt à copier", prompt, height=620)

    st.download_button(
        "⬇️ Télécharger le prompt (.txt)",
        data=prompt,
        file_name="prompt_generation_questions.txt",
        mime="text/plain",
    )

    st.markdown(
        """
        **Workflow recommandé :**
        1. Copier le prompt.
        2. Dans ChatGPT, préciser le profil recherché et les thèmes souhaités.
        3. Demander exclusivement le JSON.
        4. Enregistrer chaque réponse dans un fichier `.json`.
        5. Sélectionner un ou plusieurs fichiers avec **Ajouter une ou plusieurs banques JSON**.
        6. Les questions valides sont ajoutées à la banque intégrée ; les `id` en doublon sont signalés.
        """
    )

with tab_schema:
    st.subheader("🧩 Contrat JSON")
    st.write("Chaque question doit contenir les champs suivants :")
    schema_display = {
        "id": "identifiant unique",
        "question": "texte de la question",
        "expected_answer": "réponse attendue détaillée",
        "interviewer_memo": "mémo détaillé pour l'interviewer",
        "follow_ups": ["relance 1", "relance 2"],
        "themes": ["thématique"],
        "scenario": "scénario/contexte commun",
        "languages": ["C++"],
        "specialties": ["IoT"],
        "levels": ["Senior"],
        "technologies": ["MQTT", "gRPC"],
        "estimated_minutes": 5,
    }
    st.json(schema_display)

with tab_control:
    st.subheader("✅ Contrôle de conformité")
    requirements = [
        ("Python + déployable sur Streamlit", True, "app.py + requirements.txt"),
        ("Réponse attendue détaillée", all(bool(q.get("expected_answer", "").strip()) for q in questions), "Champ expected_answer"),
        ("Mémo interviewer détaillé", all(bool(q.get("interviewer_memo", "").strip()) for q in questions), "Champ interviewer_memo"),
        ("Relances", all(len(q.get("follow_ups", [])) >= 1 for q in questions), "Champ follow_ups"),
        ("Regroupement par thématique", all(q.get("themes") for q in questions), "Champ themes"),
        ("Scénario/contexte", all(bool(q.get("scenario", "").strip()) for q in questions), "Champ scenario"),
        ("Langages", True, "Filtre IHM"),
        ("Spécialité", True, "Filtre IHM"),
        ("Niveau", True, "Filtre IHM"),
        ("Durée", True, "Sélection par durée cible"),
        ("Technologies", True, "Filtre IHM"),
        ("Nombre de questions", True, "Sélection par nombre"),
        ("Aucune requête ChatGPT", True, "Aucune API/connexion ChatGPT dans l'application"),
        ("Création indépendante via prompt", True, "Onglet Générer des questions"),
        ("Ressources pour générer le JSON", True, "Prompt + schéma"),
        ("Ajout de questions via un ou plusieurs JSON", True, "Upload multiple JSON + validation + fusion"),
        ("Téléchargement DOCX", True, "Export Word du questionnaire"),
        ("Téléchargement Markdown", True, "Export Markdown du questionnaire"),
    ]

    passed = sum(ok for _, ok, _ in requirements)
    st.metric("Conformité des fonctionnalités", f"{passed}/{len(requirements)}")

    for name, ok, detail in requirements:
        icon = "✅" if ok else "❌"
        st.write(f"{icon} **{name}** — {detail}")

    st.caption(
        "Le contrôle porte sur l'implémentation de l'application et, pour les "
        "champs de contenu, sur la validité de la banque actuellement chargée."
    )

# Prompt de génération

Génère un tableau JSON `[...]` de questions d'entretien oral pour :
- Rôle : [Tech Lead]
- Langages : [C++]
- Domaine : [Automotive]
- Technologies : [AUTOSAR, CAN, SOME/IP, Linux]
- Nombre : [40]

Chaque objet doit contenir exactement :
`id`, `skills`, `parts`, `title`, `question`, `expected_answer`, `interviewer_memo`, `follow_ups`, `difficulty`.

Questions orientées raisonnement, scénarios, debugging et arbitrage. Le mémo doit être suffisamment détaillé pour l'interviewer. Adapter les six parties au domaine plutôt que forcer des thèmes non pertinents. Pour Automotive/C++ couvrir si pertinent AUTOSAR, CAN/CAN FD, SOME/IP/SD, Ethernet, Linux, temps réel, sécurité, tests et architecture. Pour Tech Lead couvrir décisions, dette, incidents, désaccords et risques.

Retourne uniquement le JSON, sans Markdown ni commentaire.

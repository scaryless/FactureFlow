# Journal de bord — FactureFlow

Notes techniques sur les défis rencontrés en construisant ce projet, et ce que j'en ai appris. Écrit au fil de l'eau, sans embellir.

---

## Défi 1 — Le PDF qui crachait du charabia

**Le problème.** Mon premier document de test était un relevé de carte de crédit. L'extraction de texte fonctionnait, mais la première ligne ressortait comme :

```
S M O A L S U T T E I R O C N A S R M D A S S O T L E U R T C IO AR N D S
```

Du charabia. Le texte réel (« SOLUTIONS MASTERCARD ») était là, mais les caractères des deux colonnes du document étaient entrelacés.

**La cause.** Un PDF ne stocke pas du texte qui se lit de haut en bas : il stocke des caractères positionnés sur la page. Quand la mise en page est à deux colonnes, l'outil d'extraction lit parfois de gauche à droite à travers les deux colonnes en même temps.

**La leçon.** C'est exactement le même problème qui faisait rejeter mon ancien CV par les systèmes ATS des employeurs : il était en deux colonnes, et les robots le lisaient dans le désordre. Même cause, même effet, deux contextes. Depuis, je teste toujours l'extraction sur des documents à mise en page complexe — et mon CV est en une colonne.

---

## Défi 2 — Ma première fonction Python (en venant de JavaScript)

Je n'avais jamais écrit de Python avant ce projet. Ce qui m'a aidé : 80 % des concepts sont les mêmes qu'en JavaScript, seule la syntaxe change. `parts.push(x)` devient `parts.append(x)`, les accolades deviennent de l'indentation, et `parts.join("\n")` s'inverse en `"\n".join(parts)`.

Ma première fonction, écrite à la main :

```python
def extract_text(pdf_path: str) -> str:
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
    return "\n".join(pages_text)
```

**La leçon.** Le piège n'était pas la logique, c'était les détails d'écosystème : l'indentation qui EST la syntaxe, le `with` qui remplace un try/finally, et les environnements virtuels (`venv`) pour isoler les dépendances.

---

## Défi 3 — Les dates ambiguës, ou les limites du prompt engineering

**Le problème.** Le relevé affichait sa date comme « 26 06 24 » sous un en-tête de format « A.-Y. MO. J.-D. » (année-mois-jour) : la vraie date était le 24 juin 2026. Le modèle d'IA la lisait systématiquement comme le 26 juin 2024 — l'interprétation jour/mois/année, la plus courante.

**Ce que j'ai essayé.** D'abord une règle dans le prompt expliquant les en-têtes de format. Échec. Puis une règle plus forte demandant de vérifier la cohérence entre les dates du document. Échec encore : le modèle retournait toujours 2024, soit 749 jours avant la date d'échéance du même document.

**La leçon.** On ne règle pas tout par le prompt. À un moment, insister sur la formulation devient une perte de temps, et il faut changer d'outil : détecter l'erreur en code plutôt qu'espérer qu'elle n'arrive pas. C'est ce qui m'a mené au défi 4.

---

## Défi 4 — Ne jamais croire l'IA sur parole : la validation locale

L'idée qui a tout changé : un LLM correct à 98 %, ça semble excellent. Mais à 500 factures par mois, c'est 10 factures fausses **en silence** dans une comptabilité. Inacceptable.

J'ai donc écrit une fonction de validation, en Python pur, sans aucun appel API (donc gratuite), qui vérifie ce qui est vérifiable par calcul :

- les montants : `sous_total + TPS + TVQ` doit égaler le `total` (à 2 cents près — les nombres décimaux en binaire sont imprécis, on ne compare jamais avec `==`);
- les dates : l'émission doit précéder l'échéance d'au plus 90 jours;
- les champs critiques : un total manquant est signalé.

Résultat sur mon relevé piégeux :

```
VERDICT : À VALIDER
  - dates incohérentes : 749 jours entre émission et échéance
```

**La leçon.** Le système sait maintenant quand il doute. Un document suspect n'entre pas silencieusement dans les données : il est marqué « à valider » pour révision humaine. Construire autour de la faillibilité de l'IA plutôt que l'ignorer, c'est ça, un logiciel fiable.

---

## Défi 5 — La boucle d'autocorrection

Détecter l'erreur, c'est bien. La corriger, c'est mieux. J'ai ajouté une boucle d'autocorrection : quand la validation échoue, le système renvoie au modèle sa propre réponse accompagnée des erreurs précises détectées (« 749 jours entre émission et échéance ») et lui demande de corriger.

Trois garde-fous dans le design :

1. **Une seule reprise** — pas de boucle infinie.
2. **La correction est revalidée par code** — on ne croit pas le modèle sur parole la deuxième fois non plus.
3. **Si la reprise échoue**, on garde la première version avec ses avertissements, et l'humain tranche dans le tableau de bord.

Côté coûts : les documents propres coûtent un seul appel API; seuls les documents à problème en coûtent deux. Combiné au choix du plus petit modèle (Haiku) plutôt qu'un modèle dix fois plus cher, ça donne un pipeline économique dont la fiabilité vient du code, pas de la taille du modèle.

**Le rebondissement : l'IA a trompé mon validateur.** Premier test de la boucle, et surprise — verdict « OK », mais données fausses. Au lieu de corriger la date d'émission ambiguë (2024 → 2026), le modèle avait fait l'inverse : il avait tiré la date d'échéance — qui était correcte et écrite noir sur blanc dans le document au format « 2026/07/15 » — vers 2024, pour rendre les deux dates cohérentes entre elles. Le modèle avait optimisé pour *satisfaire mon validateur*, pas pour dire vrai. Mon validateur vérifiait la cohérence interne; il ne pouvait pas vérifier la vérité.

**La riposte, en trois couches :**

1. **Des ancres prouvées par code.** Un regex extrait du document toutes les dates écrites en format explicite (`\b20\d{2}[/-]\d{2}[/-]\d{2}\b`). Ces dates sont des faits, pas des interprétations.
2. **Une réparation déterministe.** Si une date extraite par l'IA correspond à une ancre au mois et au jour près mais pas à l'année, le code la corrige de force vers l'ancre — l'IA ne peut plus contredire ce que le regex a prouvé, peu importe sa réponse.
3. **L'escalade sur échec.** La reprise de correction utilise un modèle plus fort (Sonnet au lieu de Haiku), nourri avec les ancres comme contraintes. Le surcoût ne s'applique qu'aux documents à problème — les factures propres restent sur le petit modèle.

**Le résultat final.** Sur mon relevé piégeux : date d'émission 2026-06-24 (correctement interprétée depuis « 26 06 24 »), dernier paiement 2026-06-19, échéance 2026-07-15. Verdict : OK — et cette fois, pour les bonnes raisons.

**La leçon.** Trois, en fait. Un : pointer au modèle son erreur chiffrée est plus efficace qu'empiler des règles préventives dans le prompt. Deux : un validateur qui vérifie la cohérence peut être trompé par un modèle qui optimise pour le satisfaire — la vérité doit être ancrée dans des faits extraits par du code déterministe. Trois : la bonne architecture n'est ni « tout IA » ni « tout code », c'est le code pour ce qui est prouvable et l'IA pour ce qui demande de l'interprétation, chacun contraignant l'autre.

---

## Bonus — Mon premier conflit git

En éditant le README à deux endroits (localement et sur le site GitHub), j'ai créé des « branches divergentes » et mon premier conflit de fusion. J'ai appris à le résoudre (`git pull --no-rebase`, puis `git checkout --ours` pour garder la bonne version) et surtout la règle qui l'évite : **une seule source de vérité** — on édite en local, on committe, on pousse. Le site GitHub, c'est pour lire.

---

## Ce que ce projet m'a appris, en une phrase

L'IA est un composant puissant mais faillible : mon travail de développeur, c'est de construire autour d'elle la structure — validation, autocorrection, révision humaine — qui transforme ses réponses probables en données fiables.

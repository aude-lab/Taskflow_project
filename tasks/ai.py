"""Assistant IA via l'API OpenAI.

Ce module isole toute la dépendance externe (client OpenAI, prompts système,
parsing/normalisation des réponses). Il expose deux usages métier aux vues :

- `generate_tasks(text)` — génération one-shot d'une liste de tâches à partir
  d'un texte libre (cf. SPEC-ai-assistant.md).
- `chat(messages, project_tasks=None)` — assistant conversationnel de
  planification, sortie structurée `{reply, ready_to_confirm, proposal}`
  (cf. SPEC-ai-chat.md).

Les deux ne connaissent qu'une seule exception métier : `AIServiceError`. Cet
isolement rend aussi le mock trivial en test : on patche `tasks.ai.OpenAI` (le
client), jamais d'appel réel à OpenAI.
"""
import json

from django.conf import settings
from django.utils import timezone
from openai import OpenAI, OpenAIError

from .models import Task

MODEL = "gpt-4o-mini"
# Timeout volontairement court (§4.1) : une génération qui traîne doit échouer
# proprement en 502 plutôt que de faire poireauter l'utilisateur.
TIMEOUT_SECONDS = 10

# Valeurs par défaut appliquées quand l'IA renvoie une valeur hors-choices
# (décision §5 : normaliser plutôt que rejeter, l'utilisateur corrige dans
# l'aperçu). Dérivées des choices du modèle, source unique de vérité.
_VALID_STATUS = {value for value, _ in Task.Status.choices}
_VALID_PRIORITY = {value for value, _ in Task.Priority.choices}
DEFAULT_STATUS = Task.Status.TODO
DEFAULT_PRIORITY = Task.Priority.MEDIUM

# Prompt système très explicite (demande d'Aude) : format JSON strict et valeurs
# EXACTES des choices en ASCII sans accents, pour minimiser les hallucinations.
SYSTEM_PROMPT = """\
Tu es un assistant qui transforme une description en langage naturel en une \
liste de tâches structurées pour une application de gestion de projet.

Tu dois répondre UNIQUEMENT avec un objet JSON valide, sans aucun texte avant \
ou après, sans bloc de code Markdown (pas de ```). La réponse doit être \
directement parseable par json.loads.

Format EXACT attendu :
{
  "tasks": [
    {
      "title": "chaîne courte, obligatoire, max 200 caractères",
      "description": "chaîne, peut être vide",
      "priority": "une de ces valeurs EXACTES : basse, moyenne, haute",
      "status": "une de ces valeurs EXACTES : a_faire, en_cours, termine",
      "due_date": "date au format AAAA-MM-JJ, ou null si non précisée"
    }
  ]
}

Règles impératives :
- Les valeurs de "priority" et "status" sont en ASCII SANS ACCENTS et doivent \
être EXACTEMENT celles listées ci-dessus. N'invente jamais d'autre valeur.
- Si la priorité n'est pas précisée, utilise "moyenne".
- Si le statut n'est pas précisé, utilise "a_faire".
- Si aucune échéance n'est précisée, utilise null (le mot-clé JSON null, pas \
la chaîne "null").
- "title" ne doit jamais être vide.
- Réponds toujours avec la clé "tasks" contenant une liste (éventuellement \
vide si aucune tâche n'est identifiable)."""


class AIServiceError(Exception):
    """Erreur côté service IA : OpenAI injoignable, timeout, ou réponse
    inexploitable (JSON non parseable / structure inattendue).

    La vue traduit cette exception en réponse HTTP (502 pour l'indisponibilité,
    400 pour une réponse non parseable), jamais en 500 silencieux (§4.1).
    """

    def __init__(self, message, *, unparseable=False):
        super().__init__(message)
        # `unparseable=True` : OpenAI a répondu mais son contenu est inexploitable
        # (faute du modèle) → 400. Sinon : indisponibilité du service → 502.
        self.unparseable = unparseable


def _client():
    """Instancie le client OpenAI avec la clé et le timeout configurés."""
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=TIMEOUT_SECONDS)


def _system_prompt():
    """Prompt système complété par la date du jour (serveur).

    Le modèle ne connaît pas la date courante : sans cette précision, une
    échéance relative (« vendredi prochain », « demain ») est résolue au petit
    bonheur, souvent dans le passé. On injecte donc la date du serveur au moment
    de l'appel — d'où une fonction plutôt qu'une constante.
    """
    today = timezone.localdate().isoformat()
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Nous sommes aujourd'hui le {today}. Résous toute date relative "
        f"(« demain », « vendredi prochain », « dans deux semaines ») par "
        f"rapport à cette date, et n'utilise jamais une échéance dans le passé."
    )


def _normalize_task(raw):
    """Normalise une tâche brute issue de l'IA vers des valeurs sûres (§5).

    Ne fait PAS la validation finale (longueur du titre, format exact de date) :
    celle-ci reste côté serveur au moment de la création (TaskSerializer). Ici on
    se contente de ramener status/priority dans les choices et de nettoyer les
    types, pour un aperçu propre.
    """
    if not isinstance(raw, dict):
        return None

    title = str(raw.get("title") or "").strip()
    if not title:
        # Une tâche sans titre n'a pas de sens dans l'aperçu : on l'ignore.
        return None

    priority = raw.get("priority")
    if priority not in _VALID_PRIORITY:
        priority = DEFAULT_PRIORITY

    status = raw.get("status")
    if status not in _VALID_STATUS:
        status = DEFAULT_STATUS

    # La date est laissée telle quelle (chaîne AAAA-MM-JJ) si présente ; une
    # valeur vide/absente devient null. Le format est revalidé à la création.
    due_date = raw.get("due_date")
    if not due_date:
        due_date = None

    description = raw.get("description")
    description = str(description) if description is not None else ""

    return {
        "title": title,
        "description": description,
        "priority": priority,
        "status": status,
        "due_date": due_date,
    }


def _parse_response(content):
    """Parse le contenu texte renvoyé par OpenAI en liste de tâches normalisées.

    Lève `AIServiceError(unparseable=True)` si le contenu n'est pas un JSON
    exploitable — traduit en 400 par la vue.
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise AIServiceError(
            "La réponse de l'IA n'est pas un JSON valide.", unparseable=True
        )

    # On accepte { "tasks": [...] } (format demandé) ou directement une liste,
    # par tolérance si le modèle omet l'enveloppe.
    if isinstance(data, dict):
        items = data.get("tasks")
    elif isinstance(data, list):
        items = data
    else:
        items = None

    if not isinstance(items, list):
        raise AIServiceError(
            "La réponse de l'IA n'a pas le format attendu.", unparseable=True
        )

    tasks = [normalized for item in items if (normalized := _normalize_task(item))]
    return tasks


def generate_tasks(text):
    """Interroge OpenAI et renvoie une liste de tâches normalisées (sans les créer).

    Seule fonction appelée par les vues. Toute erreur (indisponibilité, timeout,
    JSON invalide) remonte sous forme d'`AIServiceError`.
    """
    try:
        response = _client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": text},
            ],
            # Force une sortie JSON côté API : filet de sécurité complémentaire
            # du prompt contre le texte parasite.
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except OpenAIError as exc:
        # Indisponibilité, timeout, erreur d'authentification… → 502 côté vue.
        raise AIServiceError(f"Le service IA est indisponible : {exc}")

    return _parse_response(_message_content(response))


def _message_content(response):
    """Extrait le texte de la réponse OpenAI, ou lève une `AIServiceError`.

    Une réponse structurellement inattendue (aucun choix renvoyé) est traitée
    comme inexploitable plutôt que de laisser filer un IndexError en 500
    silencieux.
    """
    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError):
        raise AIServiceError(
            "La réponse de l'IA est vide ou mal formée.", unparseable=True
        )


# --- Assistant conversationnel (chat) — cf. SPEC-ai-chat.md ------------------

# Sortie TOUJOURS structurée (décision D2) : le message conversationnel vit dans
# `reply`, et la proposition finale dans `proposal` quand `ready_to_confirm`.
CHAT_SYSTEM_PROMPT = """\
Tu es un assistant de planification de projet pour l'application TaskFlow. Tu \
aides l'utilisateur à définir un projet et ses tâches par la conversation.

Réponds TOUJOURS en français.

Ton objectif est de collecter, en 2 à 4 échanges maximum (sans interrogatoire \
inutile) : le nom du projet, son objectif, le type de tâches, les priorités et \
les échéances. Pose des questions courtes et ciblées tant qu'il te manque des \
informations essentielles.

Tu dois répondre UNIQUEMENT avec un objet JSON valide, sans aucun texte avant \
ou après, sans bloc de code Markdown (pas de ```). Format EXACT :
{
  "reply": "ton message conversationnel en français, affiché à l'utilisateur",
  "ready_to_confirm": false,
  "proposal": null
}

Tant qu'il te manque des informations : "ready_to_confirm" vaut false, \
"proposal" vaut null, et "reply" contient ta question.

Dès que tu as assez d'informations pour proposer un plan complet, mets \
"ready_to_confirm" à true et remplis "proposal" ainsi :
{
  "reply": "un court récapitulatif en français",
  "ready_to_confirm": true,
  "proposal": {
    "project": {"name": "nom du projet", "description": "objectif du projet"},
    "tasks": [
      {
        "title": "chaîne courte, obligatoire, max 200 caracteres",
        "description": "chaîne, peut être vide",
        "priority": "une de ces valeurs EXACTES : basse, moyenne, haute",
        "status": "une de ces valeurs EXACTES : a_faire, en_cours, termine",
        "due_date": "date au format AAAA-MM-JJ, ou null si non précisée"
      }
    ]
  }
}

Règles impératives pour "proposal" :
- "priority" et "status" sont en ASCII SANS ACCENTS et EXACTEMENT dans les \
listes ci-dessus. N'invente jamais d'autre valeur.
- Priorité non précisée -> "moyenne" ; statut non précisé -> "a_faire" ; \
échéance non précisée -> null (le mot-clé JSON null).
- "title" ne doit jamais être vide, et "proposal.tasks" ne doit jamais être \
vide quand "ready_to_confirm" est true."""


def _chat_system_prompt(project_tasks=None):
    """Prompt système du chat, complété par la date du jour et, si le chat est
    invoqué depuis un projet existant, par ses tâches actuelles (contexte).

    `project_tasks` est un itérable d'objets `Task` (ou None). C'est la
    « mémoire » du contexte projet — pas de la conversation, qui vit côté front.
    """
    today = timezone.localdate().isoformat()
    prompt = (
        f"{CHAT_SYSTEM_PROMPT}\n\n"
        f"Nous sommes aujourd'hui le {today}. Résous toute date relative par "
        f"rapport à cette date, et n'utilise jamais une échéance dans le passé."
    )
    if project_tasks is not None:
        lines = [
            f"- {t.title} (statut: {t.status}, priorité: {t.priority}, "
            f"échéance: {t.due_date.isoformat() if t.due_date else 'aucune'})"
            for t in project_tasks
        ]
        existing = "\n".join(lines) if lines else "(aucune tâche pour l'instant)"
        prompt += (
            "\n\nContexte : ce projet existe déjà et contient les tâches "
            f"suivantes :\n{existing}\n"
            "Ta proposition doit COMPLÉTER ce projet avec de NOUVELLES tâches, "
            "sans recréer ni dupliquer les tâches existantes."
        )
    return prompt


def _parse_chat_response(content):
    """Parse la sortie structurée du chat en `{reply, ready_to_confirm,
    proposal}`, avec normalisation des tâches proposées.

    Un JSON invalide ou une structure inattendue lève `AIServiceError` (mappée en
    502 par la vue, décision D2). La proposition n'est retenue que si elle est
    exploitable (nom de projet + au moins une tâche) ; sinon on retombe
    proprement sur `ready_to_confirm: false` plutôt que de proposer un plan vide.
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise AIServiceError(
            "La réponse de l'IA n'est pas un JSON valide.", unparseable=True
        )
    if not isinstance(data, dict):
        raise AIServiceError(
            "La réponse de l'IA n'a pas le format attendu.", unparseable=True
        )

    reply = str(data.get("reply") or "").strip()
    ready = bool(data.get("ready_to_confirm"))
    raw_proposal = data.get("proposal")
    proposal = None

    if ready and isinstance(raw_proposal, dict):
        project = raw_proposal.get("project")
        project = project if isinstance(project, dict) else {}
        name = str(project.get("name") or "").strip()
        description = str(project.get("description") or "")
        raw_tasks = raw_proposal.get("tasks")
        tasks = (
            [n for t in raw_tasks if (n := _normalize_task(t))]
            if isinstance(raw_tasks, list)
            else []
        )
        if name and tasks:
            proposal = {
                "project": {"name": name, "description": description},
                "tasks": tasks,
            }

    # Une proposition annoncée mais inexploitable ne doit pas être présentée
    # comme prête à créer.
    if proposal is None:
        ready = False

    return {"reply": reply, "ready_to_confirm": ready, "proposal": proposal}


def chat(messages, project_tasks=None):
    """Poursuit la conversation de planification et renvoie la réponse structurée.

    `messages` : historique `[{role, content}, ...]` fourni par le front (déjà
    validé par le serializer). `project_tasks` : tâches du projet existant à
    injecter en contexte, ou None pour un nouveau projet. Ne crée rien : la
    création passe par les endpoints existants (projects + tasks/confirm).
    """
    api_messages = [
        {"role": "system", "content": _chat_system_prompt(project_tasks)},
        *messages,
    ]
    try:
        response = _client().chat.completions.create(
            model=MODEL,
            messages=api_messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except OpenAIError as exc:
        raise AIServiceError(f"Le service IA est indisponible : {exc}")

    return _parse_chat_response(_message_content(response))

from django_filters import rest_framework as filters

from .models import Task


class TaskFilter(filters.FilterSet):
    """Filtres de la liste des tâches (cf. tasks/SPEC-filters.md).

    Ces filtres s'appliquent au queryset déjà restreint à l'utilisateur par
    TaskViewSet.get_queryset() : ils ne peuvent que le réduire. Un `project`
    hors de la portée de l'utilisateur ne matche donc rien (liste vide), sans
    erreur ni fuite.
    """

    # `project` est un NumberFilter (et non le ModelChoiceFilter auto de
    # Meta.fields) : celui-ci valide contre Project.objects.all(), donc un pk
    # inexistant renverrait 400 alors qu'un projet d'autrui renvoie 200 [] — la
    # différence trahirait l'existence des projets d'autrui (cf. SPEC §4). Avec
    # un NumberFilter, tout pk hors du queryset utilisateur donne simplement [].
    project = filters.NumberFilter(field_name="project")

    # Bornes de date (le filtre d'égalité exacte n'est pas exposé, cf. spec).
    due_date_after = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_before = filters.DateFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Task
        # Seuls ces champs sont filtrables ; `status` et `priority` héritent des
        # choices du modèle, donc une valeur hors liste renvoie 400.
        fields = ["status", "priority", "project"]

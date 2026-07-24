from django import forms


class BootstrapFormMixin:
    """Applique la bonne classe Bootstrap à chaque widget.

    Sans elle, `{{ field }}` rend un contrôle nu au milieu de composants
    Bootstrap : le formulaire paraît non stylé. Bootstrap 5 distingue les
    `<select>` (`form-select`) des autres contrôles (`form-control`).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            bootstrap_class = (
                "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-control"
            )
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} {bootstrap_class}".strip()

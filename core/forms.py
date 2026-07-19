class BootstrapFormMixin:
    """Applique la classe Bootstrap `form-control` à tous les champs.

    Sans elle, `{{ field }}` rend un `<input>` nu au milieu de composants
    Bootstrap : le formulaire paraît non stylé.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-control".strip()

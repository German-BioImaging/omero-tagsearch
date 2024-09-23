from django.forms import Form, MultipleChoiceField, BooleanField
from django.forms import ChoiceField, RadioSelect


class TagSearchForm(Form):
    selectedTags = MultipleChoiceField()
    excludedTags = MultipleChoiceField()
    selectedKey0 = ChoiceField()
    selectedNamespaces = MultipleChoiceField()
    i = 1

    operation = ChoiceField(
        widget=RadioSelect,
        choices=(("AND", "AND"), ("OR", "OR")),
        initial="AND"
    )
    view_image = BooleanField(initial=True)
    view_dataset = BooleanField(initial=True)
    view_project = BooleanField(initial=True)
    view_well = BooleanField(initial=True)
    view_acquisition = BooleanField(initial=True)
    view_plate = BooleanField(initial=True)
    view_screen = BooleanField(initial=True)

    def set_kvp_field(self, i):
        selectedKey = ChoiceField()
        globals()[f"selectedKey{i}"] = selectedKey
        self.fields[f"selectedKey{i}"] = selectedKey

    def __init__(self, tags, keys, namespaces, conn=None, *args, **kwargs):
        super(TagSearchForm, self).__init__(*args, **kwargs)
        # Process Tags into choices (lists of tuples)
        self.fields["selectedTags"].choices = tags
        self.fields["excludedTags"].choices = tags
        self.fields["selectedKey0"].choices = keys
        self.set_kvp_field(self.i)
        self.fields[f"selectedKey{self.i}"].choices = keys
        self.fields["selectedNamespaces"].choices = namespaces
        self.conn = conn

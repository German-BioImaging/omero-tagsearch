from django.forms import Form, MultipleChoiceField, BooleanField, ChoiceField


class TagSearchForm(Form):
    selectedTags = MultipleChoiceField()
    excludedTags = MultipleChoiceField()
    operation = ChoiceField()
    results_preview = BooleanField()

    def __init__(self, tags, conn=None, *args, **kwargs):
        super(TagSearchForm, self).__init__(*args, **kwargs)

        # Process Tags into choices (lists of tuples)
        self.fields["selectedTags"].choices = tags
        self.fields["excludedTags"].choices = tags
        self.fields["operation"].choices = (("AND", "AND"), ("OR", "OR"))
        self.conn = conn

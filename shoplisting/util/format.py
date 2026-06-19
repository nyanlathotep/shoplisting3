from shoplisting.model import Ingredient, Tag

class SynthIngredient():
    def __init__(self, name):
        self.name = name

class SynthItem():
    def __init__(self, data, order):
        self.order = order
        self.ingredient = None
        ingredient = Ingredient.query.filter_by(name=data['ingredient']).first()
        if ingredient:
            self.ingredient = ingredient
        else:
            self.ingredient = SynthIngredient(data['ingredient'])
        self.amount = data.get('amount', '')
        self.unit = data.get('unit', '')

class SynthStep():
    def __init__(self, data, order):
        self.order = order
        self.instruction = data.get('instruction', '')
        self.items = []
        for i,item in enumerate(data.get('items', [])):
            self.items.append(SynthItem(item, i))

class SynthRecipe():
    def __init__(self, data):
        self.name = data.get('name', '')
        self.top_note = data.get('top_note', '')
        self.bot_note = data.get('bot_note', '')
        self.note = data.get('note', '')
        self.remark = data.get('remark', '')
        self.head_left = data.get('head_left', '')
        self.head_right = data.get('head_right', '')
        self.head_mid = data.get('head_mid', '')
        self.head_desc = data.get('head_desc', '')
        self.tags = []
        self.steps = []
        for tag_id in data.get('tags', []):
            self.tags.append(Tag.query.filter_by(id=tag_id).first())
        for i, step in enumerate(data.get('steps', [])):
            self.steps.append(SynthStep(step, i))
    @property
    def card_data(self):
        data = {
            'id': 'synth do not use',
            'name': self.name,
            'top_note': self.top_note if self.top_note else '',
            'bot_note': self.bot_note if self.bot_note else '',
            'tags': []
        }
        for tag in self.tags:
            data['tags'].append({
                'name': tag.name,
                'color': tag.color,
                'position': tag.position.name
            })
        return data

from shoplisting.model import Recipe, Category, Ingredient
from datetime import date, datetime, timedelta
import snakemd

class MDCategory():
    def __init__(self, category, parent):
        self.category = category
        self.parent = parent
        self.subcategories = {}
        self.ingredients = []
    def emit_list(self):
        data = {
            'name': self.category.name,
            'categories': [],
            'ingredients': []
        }
        for cid, cat in self.subcategories.items():
            data['categories'].append(cat.emit_list())
        for ing in self.ingredients:
            data['ingredients'].append(ing.emit_list())
        return data

class MDIngredient():
    def __init__(self, ingredient, recipe=None, special=False):
        self.ingredient = ingredient
        self.recipes = [recipe] if recipe else []
        self.category = None
        self.special = special
    def add_recipe(self, recipe):
        self.recipes.append(recipe)
    def get_heirarchy(self):
        heritage = []
        parent = self.ingredient.category
        while parent:
            heritage.append(parent.id)
            parent = parent.parent
        return reversed(heritage)
    def emit_list(self):
        show_days = len(self.recipes) > 1 or len(self.recipes) > 0 and self.special
        return {
            'name': self.ingredient.name,
            'recipes': self.recipes if show_days else None,
            'special': self.special
        }

class MDRecipe():
    def __init__(self, recipe, date):
        self.recipe = recipe
        self.date = date
    def emit_list(self):
        return {
            'name': self.recipe.name,
            'date': self.date,
            'note': self.recipe.note
        }

class MDList():
    def __init__(self, start_date):
        self.current_date = start_date
        self.recipes = []
        self.ingredients = {}
        self.subcategories = {}
    def add_recipe(self, recipe_id):
        recipe = Recipe.query.get(recipe_id)
        if self.current_date:
            day = self.current_date
            self.current_date += timedelta(days = 1)
        else:
            day = None
        md_recipe = MDRecipe(recipe, day)
        self.recipes.append(md_recipe)
        for step in recipe.steps:
            for item in step.items:
                ing = item.ingredient
                if ing.id in self.ingredients:
                    self.ingredients[ing.id].add_recipe(md_recipe)
                else:
                    self.ingredients[ing.id] = MDIngredient(ing, md_recipe)
    def add_single_item(self, item_id):
        ing = Ingredient.query.get(item_id)
        if ing.id in self.ingredients:
            self.ingredients[ing.id].special = True
        else:
            self.ingredients[ing.id] = MDIngredient(ing, special=True)
    def construct_categories(self):
        for ing_id, ing in self.ingredients.items():
            node = self
            for cat_id in ing.get_heirarchy():
                if cat_id in node.subcategories:
                    node = node.subcategories[cat_id]
                else:
                    category = Category.query.get(cat_id)
                    cat_md = MDCategory(category, node)
                    node.subcategories[cat_id] = cat_md
                    node = cat_md
            node.ingredients.append(ing)
    def emit_list(self):
        data = {
            'recipes': [],
            'categories': []
        }
        for recipe in self.recipes:
            data['recipes'].append(recipe.emit_list())
        for cid, category in self.subcategories.items():
            data['categories'].append(category.emit_list())
        return data

def render_category(category, doc, level=0, dateless=False):
    doc.add_heading(category['name'], 4 if level == 0 else 5)
    ing_list = []
    for ing in category['ingredients']:
        name = ing['name']
        if ing['recipes']:
            if dateless:
                days = len(ing['recipes'])
            else:
                days = ', '.join(datetime.strftime(recipe.date, '%a') for recipe in ing['recipes'])
            if ing['special']:
                days = '★ ' + days
            name = f'{name} ({days})'
        ing_list.append(name)
    doc.add_block(
        snakemd.MDList(ing_list, ordered=False)
    )
    for subcat in category['categories']:
        render_category(subcat, doc, level+1, dateless)

def render_markdown(slist):
    doc = snakemd.Document()
    start_date = slist['recipes'][0]['date']
    dateless = False
    if start_date:
        start_date = datetime.strftime(start_date, '%Y-%m-%d')
    else:
        start_date = ''
        dateless = True
    doc.add_heading(f'Shopping List {start_date}', 4)
    rows = []
    notes = []
    for recipe in slist['recipes']:
        name = recipe['name']
        if dateless:
            doc.add_block(snakemd.Paragraph([snakemd.Inline(name, bold=True)]))
        else:
            day = datetime.strftime(recipe['date'], '%a %Y-%m-%d')
            doc.add_block(snakemd.Paragraph([day, ' – ', snakemd.Inline(name, bold=True)]))
        if recipe['note']:
           doc.add_block(
               snakemd.MDList([snakemd.Inline(recipe['note'], italics=True)], ordered=False)
           )
    for cat in slist['categories']:
        doc.add_horizontal_rule()
        render_category(cat, doc, level=0, dateless=dateless)
    return str(doc)

def generate_slist(recipes, single_items, start_date):
    slist = MDList(start_date)
    for recipe_id in recipes:
        slist.add_recipe(recipe_id)
    for ing_id in single_items:
        slist.add_single_item(ing_id)
    slist.construct_categories()
    slist = slist.emit_list()
    md = render_markdown(slist)
    return md

from shoplisting.model import Recipe, Category, Ingredient, CategoryDisplay
from datetime import date, datetime, timedelta
import snakemd
from shoplisting.config.config import ConfigTree, load_config

class MDCategory():
    def __init__(self, category, parent):
        self.category = category
        self.parent = parent
        self.subcategories = {}
        self.ingredients = []
    def get_display(self):
        display = self.category.display
        if display != CategoryDisplay.INHERIT:
            return display
        return self.parent.get_display()
    def emit_list(self):
        data = {
            'name': self.category.name,
            'categories': [],
            'ingredients': []
        }
        display = self.get_display()
        for cid, cat in self.subcategories.items():
            subcat = cat.emit_list()
            if subcat: data['categories'].append(subcat)
        for ing in self.ingredients:
            if display == CategoryDisplay.HIDE and not ing.special:
                continue
            data['ingredients'].append(ing.emit_list())
        if not data['ingredients'] and not data['categories']: return None
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
        self.start_date = start_date
        self.current_date = start_date
        self.recipes = []
        self.ingredients = {}
        self.subcategories = {}
    def get_display(self):
        return CategoryDisplay.SHOW
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
            'start_date': self.start_date,
            'recipes': [],
            'categories': []
        }
        for recipe in self.recipes:
            data['recipes'].append(recipe.emit_list())
        for cid, category in self.subcategories.items():
            subcat = category.emit_list()
            if subcat:
                data['categories'].append(subcat)
        return data

def render_category(category, doc, cfg, level=0, dateless=False):
    max_head, min_head = cfg['slist.max_heading'], cfg['slist.min_heading']
    doc.add_heading(category['name'], max_head if level == 0 else min(min_head,max_head+level))
    ing_list = []
    for ing in category['ingredients']:
        name = ing['name']
        if ing['recipes']:
            if dateless:
                days = len(ing['recipes'])
                days = f'{days} recipes'
            else:
                days = ', '.join(datetime.strftime(recipe.date, '%a') for recipe in ing['recipes'])
            if ing['special']:
                days = f'★ {days}'
            name = f'{name} ({days})'
        ing_list.append(name)
    doc.add_block(
        snakemd.MDList(ing_list, ordered=False)
    )
    category['categories'].sort(key=lambda x:x['name'])
    for subcat in category['categories']:
        render_category(subcat, doc, cfg, level+1, dateless)

def render_markdown(slist, cfg):
    doc = snakemd.Document()
    start_date = slist['start_date']
    dateless = False
    if start_date:
        start_date = datetime.strftime(start_date, '%Y-%m-%d')
    else:
        start_date = ''
        dateless = True
    doc.add_heading(f'Shopping List {start_date}', cfg['slist.max_heading'])
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
    slist['categories'].sort(key=lambda x:x['name'])
    for cat in slist['categories']:
        doc.add_horizontal_rule()
        render_category(cat, doc, cfg, level=0, dateless=dateless)
    return str(doc)

default_slist_config = {
    'min_heading': 4,
    'max_heading': 2
}

def generate_slist(recipes, single_items, start_date):
    cfg = load_config()
    cfg.default = ConfigTree({'slist': default_slist_config })
    slist = MDList(start_date)
    for recipe_id in recipes:
        slist.add_recipe(recipe_id)
    for ing_id in single_items:
        slist.add_single_item(ing_id)
    slist.construct_categories()
    slist = slist.emit_list()
    md = render_markdown(slist, cfg)
    return md

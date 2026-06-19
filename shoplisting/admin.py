from sqlalchemy import select
from sqlalchemy.sql import func
from flask import request, jsonify, flash, redirect, url_for, Response
from flask_admin import expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.base import BaseView
from flask_admin.form import rules
from flask_admin.model.template import EndpointLinkRowAction
from wtforms.validators import Optional
import json, io, zipfile, markdown, random
from datetime import date, timedelta, datetime
from shoplisting.model import Category, Ingredient, Recipe, RecipeStep, RecipeItem, Tag, CardPage, ShoppingList, ScheduleMeal, ConfigEntry, SingleItem
from shoplisting.db import db
from .svg.svg_helper import generate_svg_batch
from .slist.csv import get_csv
from .slist.slist import generate_slist
from .ui.forms import ColorTextField
from .config.config import load_config, save_config, ConfigTree
from shoplisting.slist.slist import slist_default_config
from shoplisting.svg.svg_helper import svg_default_cfg

holiday_default_cfg = {'rules': [
    {'date': [None, 12, 25], 'message': 'Merry Christmas!'},
    {'date': [None, None, None], 'message': 'you won a prize!', 'chance': 0.25}
]}

def holiday_notifier():
    cfg = load_config()
    cfg.default = ConfigTree({'holiday': holiday_default_cfg })
    rules = cfg['holiday.rules']
    today = date.today()
    for rule in rules:
        date_parts = zip(rule['date'], (today.year, today.month, today.day))
        match = False not in [True if not x[0] else x[0] == x[1] for x in date_parts]
        if not match: continue
        if 'chance' in rule and random.random() > rule['chance']: continue
        return [{
            'message': rule['message'],
            'level': 'success'
        }]
    return None

def ingredient_notifier():
    stmt = select(func.count()).select_from(Ingredient).where(Ingredient.category_id == None)
    ing_without_cat = db.session.scalar(stmt)
    if ing_without_cat == 0: return None
    template = '{val} ingredients are missing categories.' if ing_without_cat == 1 else '{val} ingredient is missing its category.'
    return [{
        'url': '/admin/ingredient/',
        'message': template.format(val=ing_without_cat),
        'level': 'warning'
    }]

def plan_notifier():
    today = date.today()
    stmt = select(func.count()).select_from(ScheduleMeal).where(ScheduleMeal.day > today)
    pending_meals = db.session.scalar(stmt)
    if pending_meals > 2: return None
    template = 'Only {val} pending meals remaining.' if pending_meals == 1 else 'Only {val} pending meal remaining.'
    return [{
        'url': '/admin/shoppinglistview/',
        'message': template.format(val=pending_meals),
        'level': 'warning'
    }]

def card_notifier():
    recipes = Recipe.query.all()
    outdated = 0
    for r in recipes:
        if r.outdated(): outdated += 1
    if outdated == 0: return None
    template = '{val} cards need printing.' if outdated == 1 else '{val} card needs printing.'
    return [{
        'url': '/admin/cardbatchview/',
        'message': template.format(val=outdated),
        'level': 'warning'
    }]


notification_providers = [holiday_notifier, plan_notifier, ingredient_notifier, card_notifier]

class LandingPage(AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('landing_page.html')
    @expose('/api/current_slist')
    def get_active_meal_plan(self):
        slists = ShoppingList.query.all()
        today = date.today()
        active_list = None
        for slist in slists:
            if not slist.start_date: continue
            start_date = slist.start_date
            end_date = start_date + timedelta(days=len(slist.scheduled_meals)-1)
            if start_date <= today and today <= end_date:
                active_list = slist
                break
        if active_list:
            data = {'today': datetime.strftime(today, '%Y-%m-%d'), 'meals': []}
            for offset, meal in enumerate(active_list.scheduled_meals):
                data['meals'].append({
                    'date': datetime.strftime(start_date+timedelta(days=offset), '%Y-%m-%d'),
                    'weekday': datetime.strftime(start_date+timedelta(days=offset), '%A'),
                    'meal': meal.recipe.name
                })
            return jsonify(data)
        else:
            return jsonify({})
    @expose('/api/notifications')
    def get_notifications(self):
        notifs = []
        for provider in notification_providers:
            result = provider()
            if result:
                notifs.extend(result)
        return jsonify(notifs)
    @expose('/api/single_item/get')
    def get_loose_items(self):
        items = SingleItem.query.filter_by(claimed=False).order_by(SingleItem.created_at.desc()).all()
        payload = [{'name': item.ingredient.name, 'id': item.id} for item in items]
        return jsonify(payload)
    @expose('/api/single_item/add', methods=['POST'])
    def add_loose_item(self):
        data = request.get_json()
        ing = Ingredient.query.filter_by(name=data['name']).first()
        if not(ing):
            return jsonify({'success': False, 'message': 'ingredient not found'})
        si = SingleItem(ingredient = ing)
        db.session.add(si)
        db.session.commit()
        return jsonify({'success': True, 'id': si.id})
    @expose('/api/single_item/delete', methods=['POST'])
    def remove_loose_item(self):
        data = request.get_json()
        item = SingleItem.query.get(data['id'])
        if not(item):
            return jsonify({'success': False, 'message': 'item not found'})
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True})
class CategoryAdmin(ModelView):
    column_list = ('name', 'parent_path')
    column_default_sort = 'name'
    column_sortable_list = ('name', 'parent_path')
    column_labels = {'parent_path': 'Parent'}
    column_searchable_list = ('name',)
    form_excluded_columns = ('children', 'full_path', 'parent_path')
    form_rules = [
        rules.FieldSet(('name', 'parent', 'display'))
    ]
    form_args = {
        'parent': {
            'validators': [Optional()]
        }
    }

class IngredientAdmin(ModelView):
    column_list = ('name', 'category', 'recipe_count')
    column_sortable_list = ('name', ('category', 'category.full_path'), 'recipe_count')
    column_searchable_list = ('name',)
    column_default_sort = 'category.full_path'
    form_excluded_columns = ('recipe_instances',)
    form_rules = [
        rules.FieldSet(('name', 'category'))
    ]
    form_args = {
        'category': {
            'validators': [Optional()]
        }
    }

class RecipeAdmin(ModelView):
    create_template = 'recipe_editor.html'
    edit_template = 'recipe_editor.html'
    column_exclude_list = ('dmtx_id','cardsig','head_left','head_mid','head_right','head_desc')
    column_searchable_list = ('name',)
    column_extra_row_actions = [
        EndpointLinkRowAction("fa fa-print", '.render_recipe')
    ]
    @expose('/render')
    def render_recipe(self):
        recipe_id = request.args.get("id", "")
        if recipe_id:
            recipe = Recipe.query.get(recipe_id)
        if not recipe_id or not recipe:
            return 'no recipe found', 400
        return self.render(
            'recipe_print.html',
            recipe = recipe
        )

class TagAdmin(ModelView):
    form_overrides = {
        'color': ColorTextField
    }

class CardBatchView(BaseView):
    @expose('/', methods=['GET'])
    def index(self):
        raw = request.args.get('selected', '')
        selected = {int(x) for x in raw.split(',') if x.isdigit()}

        batches = CardPage.query.order_by(CardPage.created_at.desc()).all()
        recipes = Recipe.query.order_by(Recipe.name).all()
        for batch in batches:
            batch.count = len(batch.full_recipe_list)

        return self.render(
            'cards_batches.html',
            batches=batches,
            selected=selected,
            recipes=recipes
        )

    @expose('/generate', methods=['POST'])
    def generate(self):
        mode = request.form.get('mode')
        selected_ids = request.form.get('recipes', '[]')
        selected_ids = selected_ids if selected_ids else '[]'
        selected_ids = json.loads(selected_ids)

        if mode == 'needed':
            recipes = [r for r in Recipe.query.all() if r.outdated()]
            if not recipes:
                flash("No recipes require an update", "warning")
                return redirect(url_for('.index'))
        else:
            recipes = Recipe.query.filter(Recipe.id.in_(selected_ids)).all()
            if not recipes:
                flash("No recipes selected", "warning")
                return redirect(url_for('.index'))

        # generate some svgs or something
        result = generate_svg_batch(recipes)

        # Redirect back with the new batch highlighted
        return redirect(url_for('.index', selected=','.join(str(pid) for pid in result['pages'])))

    @expose('/affirm', methods=['POST'])
    def affirm(self):
        ids = request.json['ids']
        for page in CardPage.query.filter(CardPage.id.in_(ids)).all():
            page.affirm_all()
        return jsonify({'success': True})

    @expose('/delete', methods=['POST'])
    def delete(self):
        ids = request.json['ids']
        for card in CardPage.query.filter(CardPage.id.in_(ids)):
            db.session.delete(card)
        db.session.commit()
        return jsonify({'success': True})

    @expose('/download/<int:batch_id>')
    def download(self, batch_id):
        batch = CardPage.query.get_or_404(batch_id)
        return Response(
            batch.data,
            mimetype="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="cards_{batch_id}.svg"'}
        )

    @expose('/bulk_download')
    def bulk_download(self):
        raw = request.args.get('ids', '')
        ids = [int(x) for x in raw.split(',') if x.isdigit()]
        if len(ids) == 0:
            return jsonify({'success': False, 'message': 'sorry nothing'})
        elif len(ids) == 1:
            # don't batch if unnecessary to avoid confusing the userbase
            return self.download(ids[0])

        batches = CardPage.query.filter(CardPage.id.in_(ids)).all()

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as z:
            for b in batches:
                z.writestr(f"cards_{b.id}.svg", b.data)

        mem.seek(0)
        return Response(
            mem,
            mimetype='application/zip',
            headers={'Content-Disposition': 'attachment; filename="card_batches.zip"'}
        )

class ShoppingListView(BaseView):
    @expose('/', methods=['GET'])
    def index(self):
        recipes = Recipe.query.order_by(Recipe.name).all()
        default_date = date.today().isoformat()
        slists = ShoppingList.query.order_by(ShoppingList.start_date.desc()).all()
        return self.render('sl_picker.html',
            recipes = recipes,
            default_date = default_date,
            shopping_lists = slists
        )
    @expose('/parse_csv', methods=['POST'])
    def parse_csv(self):
        csv = io.StringIO(request.get_json()['text'])
        recipe_ids, invalid = get_csv(csv)
        return jsonify({'recipes': recipe_ids, 'invalid': invalid})
    @expose('/build_list', methods=['POST'])
    def generate(self):
        data = request.get_json()
        if len(data['recipes']) == 0:
            return jsonify({'success': False, 'message': 'no recipes selected'})
        dateless = data['no_schedule']
        start_date = date.fromisoformat(data['start_date']) if not dateless else None
        conflicts = []
        for offset in range(len(data['recipes'])):
            if dateless: break
            day = start_date + timedelta(days = offset)
            if ScheduleMeal.query.filter_by(day=day).first():
                conflicts.append(day)
        if conflicts:
            conflict_list = ', '.join(datetime.strftime(x, '%Y-%m-%d') for x in conflicts)
            return jsonify({'success': False, 'message': f'schedule conflicts on {conflict_list}'})
        single_items = SingleItem.query.filter_by(claimed=False).all()
        ingredients = [x.ingredient.id for x in single_items]
        md = generate_slist(data['recipes'], ingredients, start_date)
        slist = ShoppingList(start_date=start_date, markdown=md)
        db.session.add(slist)
        db.session.flush()
        for item in single_items:
            item.claimed = True
            item.slist = slist
        for offset, recipe_id in enumerate(data['recipes']):
            day = None if dateless else start_date + timedelta(days = offset)
            recipe = Recipe.query.get(recipe_id)
            meal = ScheduleMeal(day = day, slist = slist, recipe = recipe)
            db.session.add(meal)
        db.session.commit()
        return jsonify({'success': True, 'slist': slist.id})
    @expose('/render_slist')
    def render_slist(self):
        slist_id = request.args.get("id", "")
        if slist_id:
            slist = ShoppingList.query.get(slist_id)
        if not slist_id or not slist:
            return 'no recipe found', 400
        html = markdown.markdown(slist.markdown)
        return html
    @expose('/delete_slist', methods=['POST'])
    def delete_slist(self):
        slist_id = request.get_json()
        if slist_id:
            slist = ShoppingList.query.get(slist_id)
        if not slist_id or not slist:
            return {'success': False, 'message': 'no shopping list found'}
        db.session.delete(slist)
        db.session.commit()
        return jsonify({'success': True})

class ConfigAdmin(ModelView):
    list_template = 'config_list.html'
    column_list = ('key', 'value')
    @expose('/get_config/')
    def get_config(self):
        return jsonify(load_config())
    @expose('/set_config/', methods=['POST'])
    def set_config(self):
        data = request.get_json()
        cfg = ConfigTree(data)
        save_config(cfg)
        return jsonify({'success': True})

help_page = '''## Getting Started
In order to initialize the documentation from readme.md, use the [config init endpoint](/api/config/init?readme_only=true&force=true).'''

doc_default_config = {
    'help_page': help_page
}

class DocAdmin(BaseView):
    @expose('/')
    def index(self):
        default_cfg = {
            'holiday': holiday_default_cfg,
            'slist': slist_default_config,
            'svg': svg_default_cfg,
            'doc': doc_default_config
        }
        default = ConfigTree(default_cfg, delimiter = '/')
        cfg = load_config()
        cfg.default = default
        cfg.delimiter = '/'
        cfg['_default'] = default_cfg
        md = cfg['doc/help_page']
        md = md.format_map(cfg)
        html = markdown.markdown(md, extensions=['toc'])
        return self.render('markdown_page.html', content=html)

def init_admin_views(admin, db):
    admin.add_view(ShoppingListView("Shopping List"))
    admin.add_view(CategoryAdmin(Category, db))
    admin.add_view(IngredientAdmin(Ingredient, db))
    admin.add_view(RecipeAdmin(Recipe, db))
    admin.add_view(TagAdmin(Tag, db))
    admin.add_view(CardBatchView("Cards"))
    admin.add_view(ConfigAdmin(ConfigEntry, db, name = "Config"))
    admin.add_view(DocAdmin("Help"))

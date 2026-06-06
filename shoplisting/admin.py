from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.contrib.sqla import ModelView
from sqlalchemy.sql import func
from flask_admin.form import rules
from shoplisting.model import Category, Ingredient, Recipe, RecipeStep, RecipeItem, Tag, CardPage
from wtforms.validators import Optional
from shoplisting.db import db
from flask_admin import expose
from flask_admin.base import BaseView
from flask import request, jsonify, flash, redirect, url_for, Response
import json, io, zipfile
from datetime import date
from .svg.svg_helper import generate_svg_batch

# class CategoryAjaxLoader(QueryAjaxModelLoader):
#     def get_list(self, term, offset=0, limit=10):
#         query = self.session.query(self.model)
#         dist = func.fuzzy_damlev(self.model.full_path, term)
#         query = query.order_by(dist)
#         q = (
#             self.session.query(self.model, dist.label("dist"))
#             .order_by(dist)
#             .offset(offset)
#             .limit(limit)
#         )

#         results = q.all()

#         # Debug print
#         for obj, dist in results:
#             print(f"{obj.full_path} -> {dist}")
#         return query.offset(offset).limit(limit).all()

class CategoryAdmin(ModelView):
    column_list = ('name', 'parent')
    column_sortable_list = ('name', ('parent', 'parent.full_path'))
    column_searchable_list = ('name',)
    form_excluded_columns = ('children')
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
    column_exclude_list = ('dmtx_id',)
    column_searchable_list = ('name',)

class TagAdmin(ModelView):
    form_widget_args = {
        'color': {
            'type': 'color',
            'style': 'width: 100px; height: 40px; border: none; cursor: pointer;'
        }
    }

class CardBatchView(BaseView):
    @expose('/', methods=['GET'])
    def index(self):
        raw = request.args.get('selected', '')
        selected = {int(x) for x in raw.split(',') if x.isdigit()}

        batches = CardPage.query.order_by(CardPage.created_at.desc()).all()
        recipes = Recipe.query.order_by(Recipe.name).all()

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

        # Call your generator
        result = generate_svg_batch(recipes)
        print(result)
        #batch = result["batch"]  # CardBatch instance
        #db.session.add(batch)
        #db.session.commit()

        # Redirect back with the new batch highlighted
        return redirect(url_for('.index', selected=','.join(str(pid) for pid in result['pages'])))

    @expose('/download/<int:batch_id>')
    def download(self, batch_id):
        batch = CardPage.query.get_or_404(batch_id)
        return Response(
            batch.data,
            mimetype="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="cards_{batch_id}.svg"'}
        )

    @expose('/affirm/<int:batch_id>')
    def affirm(self, batch_id):
        batch = CardPage.query.get_or_404(batch_id)
        batch.affirm_all()
        flash("Page affirmed", "success")
        return redirect(url_for('.index'))

    @expose('/delete/<int:batch_id>')
    def delete(self, batch_id):
        batch = CardPage.query.get_or_404(batch_id)
        db.session.delete(batch)
        db.session.commit()
        flash("Page deleted", "success")
        return redirect(url_for('.index'))

    @expose('/bulk_download')
    def bulk_download(self):
        raw = request.args.get('ids', '')
        ids = [int(x) for x in raw.split(',') if x.isdigit()]

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

    @expose('/bulk_affirm', methods=['POST'])
    def bulk_affirm(self):
        ids = json.loads(request.form['ids'])
        for page in CardPage.query.filter(CardPage.id.in_(ids)).all():
            page.affirm_all()
        flash("Pages affirmed", "success")
        return "ok"

    @expose('/bulk_delete', methods=['POST'])
    def bulk_delete(self):
        ids = json.loads(request.form['ids'])
        for card in CardPage.query.filter(CardPage.id.in_(ids)):
            db.session.delete(card)
        db.session.commit()
        flash("Pages deleted", "success")
        return "ok"

class ShoppingListView(BaseView):
    @expose('/', methods=['GET'])
    def index(self):
        recipes = Recipe.query.order_by(Recipe.name).all()
        default_date = date.today().isoformat()
        return self.render('sl_picker.html',
            recipes = recipes,
            default_date = default_date
        )
    @expose('/parse_csv', methods=['POST'])
    def parse_csv(self):
        pass
    @expose('/build_list', methods=['POST'])
    def generate(self):
        pass

def init_admin_views(admin, db):
    admin.add_view(ShoppingListView("Shopping List"))
    admin.add_view(CategoryAdmin(Category, db))
    admin.add_view(IngredientAdmin(Ingredient, db))
    admin.add_view(RecipeAdmin(Recipe, db))
    admin.add_view(TagAdmin(Tag, db))
    admin.add_view(CardBatchView("Cards"))

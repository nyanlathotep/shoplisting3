from shoplisting.db import db
from shoplisting.model import Category, Ingredient, Tag, Recipe, RecipeStep, RecipeItem
from flask import Blueprint, jsonify, request
from sqlalchemy.sql import func

api_bp = Blueprint('api', __name__)

@api_bp.route('/category/list')
def category_list():
    tags = db.session.query(Category).all()
    data = [{'id':x.id, 'name':x.name, 'parent': x.parent.id if x.parent else None, 'full_path': x.full_path} for x in tags]
    return jsonify(data)

@api_bp.route('/category/create', methods=['POST'])
def category_create():
    data = request.get_json()
    obj = Category(
        name = data.get('name',''),
        parent_id = data.get('parent',None)
    )
    db.session.add(obj)
    db.session.flush()
    db.session.commit()
    return jsonify({'success':True, 'id': obj.id})

@api_bp.route('/ingredient/search')
def ingredient_search():
    q = request.args.get("q", "")
    if not q:
        return jsonify([])
    dist = func.fuzzy_damlev(Ingredient.name, q)
    results = (
        db.session.query(Ingredient.name)
        .order_by(dist)
        .limit(10)
        .all()
    )
    return jsonify([r[0] for r in results])

@api_bp.route('/tag/list')
def tag_list():
    tags = db.session.query(Tag).all()
    data = [{'id':x.id, 'name':x.name, 'position':x.position.name} for x in tags]
    return jsonify(data)

@api_bp.route('/tag/create', methods=['POST'])
def tag_create():
    data = request.get_json()
    obj = Tag(
        name = data.get('name',''),
        color = data.get('color',''),
        position = data.get('position', 'TOP_LEFT')
    )
    db.session.add(obj)
    db.session.flush()
    db.session.commit()
    return jsonify({'success':True, 'id': obj.id})

@api_bp.route('/ingredient/set_category', methods=['POST'])
def set_ingredient_category():
    data = request.get_json()
    ing_id = data.get('ingredient', None)
    cat_id = data.get('category', None)
    if not ing_id:
        return jsonify({'success': False, 'error': 'no category specified'}), 400
    ing = Ingredient.query.get(ing_id)
    ing.category_id = cat_id
    db.session.merge(ing)
    db.session.commit()
    return jsonify({'success':True})

@api_bp.route('/recipe/get')
def load_json():
    recipe_id = request.args.get("id", "")
    if recipe_id:
        recipe = Recipe.query.get(recipe_id)
    if not recipe_id or not recipe:
        return 'no recipe found', 400
    data = {}
    data['id'] = recipe.id
    data['name'] = recipe.name
    data['top_note'] = recipe.top_note
    data['bot_note'] = recipe.bot_note
    data['note'] = recipe.note
    data['remark'] = recipe.remark
    data['tags'] = [x.id for x in recipe.tags]
    data['steps'] = []
    for step in recipe.steps:
        data_step = {
            'instruction': step.instruction,
            'items': []
        }
        for item in step.items:
            data_step['items'].append({
                'ingredient': Ingredient.query.get(item.ingredient_id).name,
                'amount': item.amount,
                'unit': item.unit
            })
        data['steps'].append(data_step)
    return jsonify(data)

@api_bp.route('/recipe/save', methods=['POST'])
def save_json():
    data = request.get_json()
    recipe_id = data['id'] if 'id' in data else None
    if recipe_id:
        recipe = Recipe.query.get(recipe_id)
    else:
        recipe = Recipe()
    recipe.name = data.get('name', '')
    recipe.top_note = data.get('top_note', '')
    recipe.bot_note = data.get('bot_note', '')
    recipe.note = data.get('note', '')
    recipe.remark = data.get('remark', '')

    db.session.add(recipe)
    db.session.flush()

    for tag_id in data['tags']:
        tag = Tag.query.filter_by(id=tag_id).first()
        recipe.tags.append(tag)

    for step in RecipeStep.query.filter_by(recipe_id=recipe.id).all():
        db.session.delete(step)

    new_ingredients = []
    for i,step_data in enumerate(data['steps'], start=1):
        step = RecipeStep(
            recipe_id = recipe.id,
            order = i,
            instruction = step_data['instruction']
        )
        db.session.add(step)
        db.session.flush()
        for j,item in enumerate(step_data['items'], start=1):
            ingredient = Ingredient.query.filter_by(name=item['ingredient']).first()
            if not ingredient:
                ingredient = Ingredient(name=item['ingredient'])
                db.session.add(ingredient)
                db.session.flush()
                new_ingredients.append({'name': ingredient.name, 'id': ingredient.id})
            db.session.add(RecipeItem(
                step_id = step.id,
                ingredient_id = ingredient.id,
                amount = item.get('amount',''),
                unit = item.get('unit',''),
                order = j
            ))
    db.session.commit()
    return jsonify({'success': True, 'redirect': '/admin/recipe/', 'new_ingredients': new_ingredients})

@api_bp.route('/recipe/card_data')
def recipe_card_data():
    cards = []
    for recipe in Recipe.query.all():
        card = {
            'name': recipe.name,
            'top_note': recipe.top_note,
            'bot_note': recipe.bot_note,
            'id': recipe.id,
            'tags': []
        }
        for tag in recipe.tags:
            card['tags'].append({
                'name': tag.name,
                'color': tag.color,
                'position': tag.position.name
            })
        cards.append(card)
    return(jsonify(cards))

@api_bp.route('/recipe/recompute_signatures')
def recipe_recompute_sigs():
    for recipe in Recipe.query.all():
        recipe.update_cardsig()
    db.session.commit()
    return 'ok'

@api_bp.route('/oh/no')
def nuclear_option():
    for recipe in Recipe.query.all():
        db.session.delete(recipe)
    for ingredient in Ingredient.query.all():
        db.session.delete(ingredient)
    for tag in Tag.query.all():
        db.session.delete(tag)
    for category in Category.query.all():
        db.session.delete(category)
    db.session.commit()
    return 'ok'

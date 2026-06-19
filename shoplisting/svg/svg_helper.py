from flask import current_app
import os.path
from shoplisting.model import CardPage, CardSig
from shoplisting.db import db
from shoplisting.config.config import ConfigTree, load_config
from .svg_render import SvgPage

svg_default_cfg = {
    'page': {
        'size': [8.5, 11],
        'dpi': 96,
        'cardgrid': [4,3],
        'margin': [0.5, 0.5]
    },
    'typeface': {
        'family': 'Liberation Sans',
        'ttfpath': 'LiberationSans-Rg.otf',
        'card': {
            'flagsize': 16,
            'notesize': 18,
            'timesize': 18,
            'titlesize': 24,
            'dmtxsize': 4.5
        }
    },
    'card': {
        'flag': {
            'offset': 0.1,
            'size': [0.6, 0.15]
        },
        'circle': {
            'pos': [0.5, 0.1],
            'r': 0.03
        },
        'title': {
            'box': [0.05, 0.28, 0.9, 0.36],
            'box_r': 0.04,
            'titlepos': [0.5, 0.36],
            'notepos': [0.5, 0.70],
            'timepos': [0.5, 0.27],
            'color': 'black'
        },
        'dmtx': {
            'box': [0.4, 0.82, 0.2, 0.2],
            'labelpos': [0.5, 0.85]
        }
    }
}

# single page of recipes to SVG only
def generate_svg_page(recipes,cfg=None):
    if not cfg:
        cfg = load_config()
    cfg.default = ConfigTree({'svg': svg_default_cfg })
    cfg['svg.typeface.ttfpath'] = os.path.join(current_app.static_folder, cfg['svg.typeface.ttfpath'])
    page = SvgPage(cfg)
    for recipe in recipes:
        card = recipe.card_data
        page.addcard(card)
    return page.svg_data()

# auto-batches arbitrary number of recipes, rendering them to SVG
# and saving the pages and signatures to db
def generate_svg_batch(recipes):
    cfg = load_config()
    cfg.default = ConfigTree({'svg': svg_default_cfg })
    page_batch = cfg['svg.page.cardgrid']
    page_batch = page_batch[0] * page_batch[1]
    pages = []
    for i in range(0, len(recipes), 12):
        batch = recipes[i:min(i+12,len(recipes))]
        signatures = []
        recipe_ids = set()
        svg = generate_svg_page(batch)
        card_page = CardPage(data = svg)
        db.session.add(card_page)
        db.session.flush()
        for recipe in batch:
            if recipe.id in recipe_ids:
                continue
            recipe_ids.add(recipe.id)
            signatures.append(CardSig(
                signature = recipe.cardsig,
                recipe = recipe,
                page = card_page
            ))
        db.session.add_all(signatures)
        db.session.commit()
        pages.append(card_page)
    return {'success': True, 'pages': [x.id for x in pages]}

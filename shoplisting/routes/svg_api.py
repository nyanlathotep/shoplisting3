from shoplisting.db import db
from flask import Blueprint, jsonify, request
import requests
from .svg_helper import SvgPage

svg_api_bp = Blueprint('svg_api', __name__)

svg_cfg = {
    'page': {
        'size': [8.5, 11],
        'dpi': 96,
        'cardgrid': [4,3],
        'margin': [0.5, 0.5]
    },
    'typeface': {
        'family': 'calibri',
        'ttfpath': 'C:\Windows\Fonts\calibri.ttf',
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

@svg_api_bp.route('/card/draw', methods=['POST'])
def draw_cards():
    card_data = request.get_json()
    page = SvgPage(svg_cfg)
    for card in card_data[:12]:
        page.addcard(card)
    return page.svg_data()

@svg_api_bp.route('/card/test')
def test_cards():
    card_data = requests.get('http://localhost:5000/api/recipe/card_data').json()
    svg_data = requests.post('http://localhost:5000/api/card/draw', json=card_data).text
    return svg_data

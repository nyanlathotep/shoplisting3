from flask import Blueprint, jsonify, request
import requests
from shoplisting.db import db
from shoplisting.util.format import SynthRecipe
from shoplisting.svg.svg_helper import generate_svg_page
from shoplisting.config.config import ConfigTree, load_config

svg_api_bp = Blueprint('svg_api', __name__)

def set_preview_override(cfg):
    size = cfg['svg.page.size']
    margin = cfg['svg.page.margin']
    grid = cfg['svg.page.cardgrid']
    cfg['svg.page.size'] = ((size[0]-margin[0])/grid[0],(size[1]-margin[1])/grid[1])
    cfg['svg.page.grid'] = (1,1)
    cfg['svg.page.margin'] = (0,0)

@svg_api_bp.route('/card/draw_preview', methods=['POST'])
def draw_preview():
    # attempted to draw a smaller canvas with a single card, but had rendering issues
    # cropping viewport clientside instead
    #cfg = load_config()
    #set_preview_override(cfg)
    data = request.get_json()
    recipe = SynthRecipe(data)
    svg = generate_svg_page([recipe])
    return svg 

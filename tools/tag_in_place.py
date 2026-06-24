import requests
import re

# simple mass-tagging script to add one tag to all recipes in db

server = '10.0.0.20:5000'
tag_to_add = 30

page_id = 0
recipe_ids = []
while True:
    r = requests.get(f'http://{server}/admin/recipe/', params={'page':page_id})
    matches = list(re.finditer(r'href="\/admin\/recipe\/edit\/\?id=(\d+)', r.text))
    if len(matches) == 0:
        break
    for match in matches:
        recipe_ids.append(match.group(1))
    page_id += 1

for recipe_id in recipe_ids:
    recipe = requests.get(f'http://{server}/api/recipe/get',params={'id':recipe_id}).json()
    if tag_to_add not in recipe['tags']:
        recipe['tags'].append(tag_to_add)
    recipe['id'] = recipe_id
    resp = requests.post(f'http://{server}/api/recipe/save', json=recipe)
    if resp.status_code != 200:
        print(resp.status_code, resp.text, recipe_id, recipe)
        exit(0)
print(f'{len(recipe_ids)} recipes successfully tagged')

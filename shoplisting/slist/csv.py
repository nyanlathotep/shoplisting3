import datetime, csv
from collections import namedtuple
from shoplisting.model import Recipe

def get_timestamp(string, fmt):
  return datetime.datetime.strptime(string, fmt)

def csv_tapmedia(row):
  datestring = '{} {}'.format(row[2], row[3])
  ts = get_timestamp(datestring, '%m/%d/%Y %H:%M:%S')
  return row[1], row[0], ts

def csv_dimai(row):
  ts = get_timestamp(row[0], '%Y-%m-%d %H:%M:%S')
  return row[2], row[1], ts

parsers = {
  ('Name', 'Text', 'Date', 'Time'): csv_tapmedia,
  ('Date', 'Format', 'Text'): csv_dimai
}

def get_csv(fp):
  reader = csv.reader(fp)
  header = tuple(x.strip() for x in reader.__next__())
  recipes = []
  invalid = []
  parser = parsers[header]
  scans = []
  for row in reader:
    scan = parser(row)
    scans.append((scan))
  scans.sort(key= lambda x: x[2])
  for scan in scans:
    dmtx, codetype, timestamp = scan
    recipe = Recipe.query.filter_by(dmtx_id=dmtx).first()
    if recipe:
      recipes.append(recipe.id)
    else:
      invalid.append(dmtx)
  return recipes, invalid

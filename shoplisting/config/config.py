import json
from collections import defaultdict
from shoplisting.model import ConfigEntry
from shoplisting.db import db

def serialize_tree(node, root_path=[]):
    keys = {}
    for k,v in node.items():
        if isinstance(v, dict):
            keys.update(serialize_tree(v, root_path+[k]))
        else:
            path = root_path+[k]
            keys['.'.join(path)] = json.dumps(v)
    return keys

class ConfigTree():
    def __init__(self, tree=None, default=None):
        self.tree = tree if tree else {}
        self.default = default
    def __getitem__(self, k):
        path = k.split('.')
        node = self.tree
        try:
            for tag in path:
                node = node[tag]
            return node
        except KeyError:
            if self.default:
                return self.default[k]
            else:
                raise
    def __setitem__(self, k, v):
        path = k.split('.')
        node = self.tree
        for tag in path[:-1]:
            if tag not in node:
                node[tag] = {}
            node = node[tag]
        node[path[-1]] = v
    def serialize_values(self):
        return serialize_tree(self.tree)
    def deserialize_values(self, entries):
        for k,v in entries.items():
            self[k] = json.loads(v)

def load_config():
    entries = {}
    for entry in ConfigEntry.query.all():
        entries[entry.key] = entry.value
    cfg = ConfigTree()
    cfg.deserialize_values(entries)
    return cfg

def save_config(cfg):
    for key, value in cfg.serialize_values().items():
        entry = ConfigEntry.query.get(key)
        if entry:
            entry.value = value
        else:
            entry = ConfigEntry(key = key, value = value)
            db.session.add(entry)
    db.session.commit()
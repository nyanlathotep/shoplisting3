from typing import List
import enum
from sqlalchemy import Enum, ForeignKey, Table, Column, select, literal_column, update, event, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased, Session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from shoplisting.db import db
from datetime import datetime, date, timedelta
import hashlib, json, string, re
from shoplisting.util.math import base36

class CategoryDisplay(enum.Enum):
    INHERIT = 1
    HIDE = 2
    SHOW = 3

class Category(db.Model):
    __tablename__ = "store_category"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    parent_id: Mapped[int] = mapped_column(ForeignKey("store_category.id"), nullable=True)
    parent: Mapped["Category"] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[List["Category"]] = relationship(back_populates="parent")
    display: Mapped[CategoryDisplay] = mapped_column(Enum(CategoryDisplay),
        server_default=CategoryDisplay.INHERIT.name)
    # cached string properties of the heirarchy for sorting
    full_path: Mapped[str] = mapped_column(server_default='')
    parent_path: Mapped[str] = mapped_column(server_default='')
    def update_full_path(self):
        node = self
        parts = []
        while node:
            parts.append(node.name)
            node = node.parent
        self.full_path = " » ".join(reversed(parts))
        # end me.
        self.parent_path = " » ".join(reversed(parts[1:]))
        for child in self.children:
            child.update_full_path()
    def __str__(self):
        return self.full_path     

# listens for Category insert or .name/.parent update
# triggers update_full_path to update cached full_path/parent_path
@event.listens_for(Category, "before_insert")
def also_full_path_on_insert_because_this_is_hell(mapper, connection, target):
    with Session(bind=connection) as session:
        target.update_full_path()
        session.commit()
@event.listens_for(Category.parent_id, "set")
def category_parent_change(target, value, oldvalue, initiator):
    if value == oldvalue: return
    target._needs_path_update = True
@event.listens_for(Category.name, "set")
def category_name_change(target, value, oldvalue, initiator):
    if value == oldvalue: return
    target._needs_path_update = True
@event.listens_for(db.session, "after_flush_postexec")
def update_path_values(session, flush_context):
    for obj in session.identity_map.values():
        if isinstance(obj, Category) and getattr(obj, "_needs_path_update", False):
            obj.update_full_path()
            del obj._needs_path_update

class Ingredient(db.Model):
    __tablename__ = "ingredient"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    category_id: Mapped[int] = mapped_column(ForeignKey("store_category.id"), nullable=True)
    category: Mapped["Category"] = relationship()
    recipe_instances: Mapped[List["RecipeItem"]] = relationship(back_populates="ingredient")
    # used for recipe count display on view
    @hybrid_property
    def recipe_count(self):
        return len(self.recipe_instances)
    @recipe_count.expression
    def recipe_count(cls):
        return (
            select(func.count(RecipeItem.id))
            .where(RecipeItem.ingredient_id == cls.id)
            .label("recipe_count")
        )

class TagCorner(enum.Enum):
    TOP_LEFT = 1
    TOP_RIGHT = 2
    BOT_LEFT = 4
    BOT_RIGHT = 8

class Tag(db.Model):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    position: Mapped[TagCorner] = mapped_column(Enum(TagCorner),
        server_default=TagCorner.TOP_LEFT.name)
    color: Mapped[str] = mapped_column()
    def __str__(self):
        ps = ''.join(x[0] for x in self.position.name.split('_'))
        return f'<{ps}> {self.name}'

# association table for recipe tags relation
recipe_tag_table = Table(
    "recipe_tag_table",
    db.metadata,
    Column('recipe_id', ForeignKey('recipe.id'), primary_key=True),
    Column('tag_id', ForeignKey('tag.id'), primary_key=True)
)

### recipe

# base id, strips non-dmtx text mode characters
def dmtx_base_id(name):
    base_dmtx = re.sub(r'[^a-z0-9\s]+', '', name.lower())
    return re.sub(r'\s+', ' ', base_dmtx).strip()

# unique readable dmtx id generator, first tries r_ prefix + base id (max 16 chars)
# if fails, adds a base36 encoded version of the recipe id to the prefix
# if that fails, adds an incrementing base36 suffix to the end until it works
# probably will never really be needed
def unique_dmtx_id(session, recipe):
    base_dmtx = dmtx_base_id(recipe.name)
    dmtx = 'r ' + base_dmtx[:14]
    exists = session.scalar(
        select(Recipe).where(Recipe.dmtx_id == dmtx)
    )
    if not exists: return dmtx
    prefix = f'r{base36.to_base(recipe.id) }'
    dmtx = prefix + base_dmtx[:16-len(prefix)]
    exists = session.scalar(
        select(Recipe).where(Recipe.dmtx_id == dmtx)
    )
    if not exists: return dmtx
    i = 0
    while exists:
        suffix = base36.to_base(i)
        dmtx = prefix + base_dmtx[:16-len(prefix)-len(suffix)] + suffix  
        exists = db.session.scalar(
            select(model).where(column == dmtx)
        )
    return dmtx

class Recipe(db.Model):
    __tablename__ = "recipe"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    steps: Mapped[List["RecipeStep"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    # card data
    dmtx_id: Mapped[str] = mapped_column(unique=True, nullable=True)
    top_note: Mapped[str] = mapped_column(nullable=True)
    bot_note: Mapped[str] = mapped_column(nullable=True)
    tags: Mapped[List[Tag]] = relationship(secondary=recipe_tag_table)
    cardsig: Mapped[str] = mapped_column()
    # note rendered on shopping list
    note: Mapped[str] = mapped_column(nullable=True)
    # database-only note
    remark: Mapped[str] = mapped_column(nullable=True)
    # gathers all relevant data for the printed card into an object
    @hybrid_property
    def card_data(self):
        data = {
            'id': self.dmtx_id,
            'name': self.name,
            'top_note': self.top_note if self.top_note else '',
            'bot_note': self.bot_note if self.bot_note else '',
            'tags': []
        }
        for tag in self.tags:
            data['tags'].append({
                'name': tag.name,
                'color': tag.color,
                'position': tag.position.name
            })
        return data
    # computes a stable hash of the card_data
    # for determining what cards need reprinting
    def get_cardsig(self):
        dat = self.card_data
        dat['tags'].sort(key=lambda x: x['name'])
        dat = json.dumps(dat, sort_keys=True)
        return hashlib.sha256(dat.encode('ascii')).hexdigest()
    def update_cardsig(self):
        self.cardsig = self.get_cardsig()
    # uses cardsigs to determine what cards have changed
    def outdated(self):
        current_sig = self.cardsig
        last_sig = CardSig.query \
            .filter_by(recipe_id=self.id) \
            .filter(CardSig.affirmed_at.isnot(None)) \
            .order_by(CardSig.affirmed_at.desc()).first()
        if not last_sig: return True
        return current_sig != last_sig.signature

# auto-assigns a dmtx ID when inserting recipes
@event.listens_for(Recipe, "before_insert")
def assign_dmtx_id(mapper, connection, target):
    if target.dmtx_id is None:
        with Session(bind=connection) as session:
            target.dmtx_id = unique_dmtx_id(session, target)
            session.commit()
# update cardsig on insert
@event.listens_for(Recipe, "before_insert")
def recipe_insert_listener(mapper, connection, target):
    with Session(bind=connection) as session:
        target.update_cardsig()
        session.commit()
# listen for the million billion things that change cardsig
@event.listens_for(Recipe.name, "set")
def recipe_name_change(target, value, oldvalue, initiator):
    if value == oldvalue: return
    target._needs_sig_update = True
@event.listens_for(Recipe.top_note, "set")
def recipe_tnote_change(target, value, oldvalue, initiator):
    if value == oldvalue: return
    target._needs_sig_update = True
@event.listens_for(Recipe.bot_note, "set")
def recipe_bnote_change(target, value, oldvalue, initiator):
    if value == oldvalue: return
    target._needs_sig_update = True
@event.listens_for(Recipe.tags, "append")
def recipe_tag_add(target, value, oldvalue, initiator):
    target._needs_sig_update = True
@event.listens_for(Recipe.tags, "remove")
def recipe_tag_del(target, value, oldvalue, initiator):
    target._needs_sig_update = True
# update cardsig on flush
@event.listens_for(db.session, "after_flush_postexec")
def recipe_change_listener(session, flush_context):
    for obj in session.identity_map.values():
        if isinstance(obj, Recipe) and getattr(obj, "_needs_sig_update", False):
            obj.update_cardsig()
            del obj._needs_path_update
# ooh look at me, I'm an ORM, what do I do, manage objects? no.

# recipe subcomponents
class RecipeStep(db.Model):
    __tablename__ = "recipe_step"
    id: Mapped[int] = mapped_column(primary_key=True)
    instruction: Mapped[str] = mapped_column()
    order: Mapped[int] = mapped_column()
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"))
    recipe: Mapped["Recipe"] = relationship(back_populates="steps")
    items: Mapped[List["RecipeItem"]] = relationship(back_populates="step", cascade="all, delete-orphan")

class RecipeItem(db.Model):
    __tablename__ = "recipe_ingredient"
    id: Mapped[int] = mapped_column(primary_key=True)
    order: Mapped[int] = mapped_column()
    amount: Mapped[str] = mapped_column()
    unit: Mapped[str] = mapped_column()
    step_id: Mapped[int] = mapped_column(ForeignKey("recipe_step.id"))
    step: Mapped["RecipeStep"] = relationship(back_populates="items")
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.id"))
    ingredient: Mapped["Ingredient"] = relationship(back_populates="recipe_instances")

# stable hash values for cards, stored to decide when cards need generation
class CardSig(db.Model):
    __tablename__ = "card_signature"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    signature: Mapped[str] = mapped_column()
    affirmed_at: Mapped[datetime] = mapped_column(nullable=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"))
    recipe: Mapped["Recipe"] = relationship()
    page_id: Mapped[int] = mapped_column(ForeignKey("svg_page.id"), nullable=True)
    page: Mapped["CardPage"] = relationship(back_populates="signatures")

class CardPage(db.Model):
    __tablename__ = "svg_page"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    data: Mapped[str] = mapped_column()
    affirmed: Mapped[bool] = mapped_column(server_default='0')
    signatures: Mapped[List["CardSig"]] = relationship(back_populates="page", passive_deletes=True)
    # list of recipe names for display on view
    @hybrid_property
    def recipe_list(self, full=False):
        recipe_names = [x.recipe.name for x in self.signatures]
        text = ', '.join(recipe_names)
        if full: return text
        if len(text) > 80:
            text = text[:77] + '...'
        return text
    def affirm_all(self):
        if self.affirmed: return
        for sig in self.signatures:
            sig.affirmed_at = func.now()
        self.affirmed = True
        db.session.commit()

# delete associated signatures only if the page is not affirmed
# affirmed signatures are meant to be cards in circulation
# so they need to be kept even if the svg is dumped
@event.listens_for(CardPage, "before_delete")
def cardpage_signature_check(mapper, connection, target):
    # delete unaffirmed child signatures
    if not target.affirmed:
        connection.execute(
            CardSig.__table__.delete().where(
                (CardSig.page_id == target.id)
            )
        )
    else:
        connection.execute(
            CardSig.__table__.update().where(
                (CardSig.page_id == target.id)
            )
            .values(page_id=None)
        )

# a meal scheduled on a specific day associated with a shopping list
class ScheduleMeal(db.Model):
    __tablename__ = "meal_schedule"
    id: Mapped[int] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(nullable=True)
    slist_id: Mapped[int] = mapped_column(ForeignKey("shopping_list.id"))
    slist: Mapped["ShoppingList"] = relationship(back_populates="scheduled_meals")
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipe.id"))
    recipe: Mapped["Recipe"] = relationship()

class ShoppingList(db.Model):
    __tablename__ = "shopping_list"
    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    markdown: Mapped[str] = mapped_column()
    scheduled_meals: Mapped[List["ScheduleMeal"]] = relationship(back_populates="slist", cascade="all, delete-orphan")
    single_items: Mapped[List["SingleItem"]] = relationship(back_populates="slist")
    # list of associated meals for display on the view
    @hybrid_property
    def recipe_list(self, full=False):
        recipe_names = [x.recipe.name for x in self.scheduled_meals]
        text = ', '.join(recipe_names)
        if full: return text
        if len(text) > 80:
            text = text[:77] + '...'
        return text
    @hybrid_property
    def end_date(self):
        if self.start_date:
            n_days = len(self.scheduled_meals)
            return self.start_date + timedelta(days = n_days-1)

class ConfigEntry(db.Model):
    __tablename__ = "config_entry"
    #id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column()

class SingleItem(db.Model):
    __tablename__ = "single_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredient.id"))
    ingredient: Mapped["Ingredient"] = relationship()
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    claimed: Mapped[bool] = mapped_column(default=False)
    slist_id: Mapped[int] = mapped_column(ForeignKey("shopping_list.id"),nullable=True)
    slist: Mapped["ShoppingList"] = relationship(back_populates="single_items")

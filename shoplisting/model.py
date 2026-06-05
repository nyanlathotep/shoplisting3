from typing import List
import enum
from sqlalchemy import Enum, ForeignKey, Table, Column, select, literal_column, update, event
from sqlalchemy.orm import Mapped, mapped_column, relationship, aliased
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from shoplisting.db import db
from datetime import datetime
import hashlib, json

class Category(db.Model):
    __tablename__ = "store_category"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    parent_id: Mapped[int] = mapped_column(ForeignKey("store_category.id"), nullable=True)
    parent: Mapped["Category"] = relationship(back_populates="children", remote_side=[id])
    children: Mapped[List["Category"]] = relationship(back_populates="parent")
    @hybrid_property
    def full_path(self):
        node = self
        parts = []
        while node:
            parts.append(node.name)
            node = node.parent
        return " / ".join(reversed(parts))
    # @full_path.expression
    # def full_path(self):
    #     parent = aliased(self)
    #     return (
    #         select(func.group_concat(parent.name, ' / '))
    #         .where(parent.id == self.id)
    #         .correlate(self)
    #         .scalar_subquery()
    #     )
    def __str__(self):
        return self.full_path

class Ingredient(db.Model):
    __tablename__ = "ingredient"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    category_id: Mapped[int] = mapped_column(ForeignKey("store_category.id"), nullable=True)
    category: Mapped["Category"] = relationship()
    recipe_instances: Mapped[List["RecipeItem"]] = relationship()

class TagCorner(enum.Enum):
    TOP_LEFT = 1
    TOP_RIGHT = 2
    BOT_LEFT = 4
    BOT_RIGHT = 8

class Tag(db.Model):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    position: Mapped[TagCorner] = mapped_column(Enum(TagCorner))
    color: Mapped[str] = mapped_column()
    def __str__(self):
        ps = ''.join(x[0] for x in self.position.name.split('_'))
        return f'<{ps}> {self.name}'

recipe_tag_table = Table(
    "recipe_tag_table",
    db.metadata,
    Column('recipe_id', ForeignKey('recipe.id'), primary_key=True),
    Column('tag_id', ForeignKey('tag.id'), primary_key=True)
)

class Recipe(db.Model):
    __tablename__ = "recipe"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    steps: Mapped[List["RecipeStep"]] = relationship(back_populates="recipe", cascade="all, delete-orphan")
    top_note: Mapped[str] = mapped_column(nullable=True)
    bot_note: Mapped[str] = mapped_column(nullable=True)
    note: Mapped[str] = mapped_column(nullable=True)
    remark: Mapped[str] = mapped_column(nullable=True)
    tags: Mapped[List[Tag]] = relationship(secondary=recipe_tag_table)
    @hybrid_property
    def card_data(self):
        data = {
            'id': self.id,
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
    @hybrid_property
    def card_sig(self):
        dat = self.card_data
        dat['tags'].sort(key=lambda x: x['name'])
        dat = json.dumps(dat, sort_keys=True)
        return hashlib.sha256(dat.encode('ascii')).hexdigest()
    def outdated(self):
        current_sig = self.card_sig
        last_sig = CardSig.query \
            .filter_by(recipe_id=self.id) \
            .filter(CardSig.affirmed_at.isnot(None)) \
            .order_by(CardSig.affirmed_at.desc()).first()
        if not last_sig: return True
        return current_sig != last_sig.signature

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

# page_recipe_table = Table(
#     "page_recipe_table",
#     db.metadata,
#     Column('page_id', ForeignKey('svg_page.id'), primary_key=True),
#     Column('recipe_id', ForeignKey('recipe.id'), primary_key=True)
# )

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
    #recipes: Mapped[List[Recipe]] = relationship(secondary=page_recipe_table)
    signatures: Mapped[List["CardSig"]] = relationship(back_populates="page", passive_deletes=True)
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

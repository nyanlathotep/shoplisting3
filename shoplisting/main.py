from flask import Flask, render_template
from flask_migrate import Migrate
from flask_admin import Admin
from sqlalchemy import event
from shoplisting.db import db
import glob, os.path
from .routes.data_api import api_bp

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///shoplisting.db"
app.config['SECRET_KEY'] = 'okay'

migrate = Migrate(app, db)
migrate.init_app(app, db, render_as_batch=True)

db.init_app(app)
with app.app_context():
    engine = db.engine
    # load required sqlean extensions
    LOAD_EXTENSIONS = ['fuzzy']
    @event.listens_for(engine, "connect")
    def load_extensions(db_conn, conn_record):
        print('loading extensions')
        db_conn.enable_load_extension(True)
        for path in glob.glob('extensions/*'):
            basename = os.path.splitext(os.path.split(path)[1])[0]
            if basename in LOAD_EXTENSIONS:
                db_conn.load_extension(path)
                print(f'loaded extension {basename} from {path}')
        db_conn.enable_load_extension(False)
    db.create_all()

    from shoplisting.admin import init_admin_views, LandingPage
    admin = Admin(app, name='shoplisting', index_view=LandingPage())
    init_admin_views(admin, db)

app.register_blueprint(api_bp, url_prefix='/api')
#app.register_blueprint(svg_api_bp, url_prefix='/api')

def start_server():
    app.run(host='0.0.0.0', port=5000)

@app.route("/")
def homepage():
    return 'hi'

@app.route("/scan")
def scan():
    return render_template('sl_picker.html')
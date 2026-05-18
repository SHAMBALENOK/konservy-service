from flask import Flask
from routers.rootnhealth import rootnhealth

app = Flask(__name__)
app.register_blueprint(simple_page)
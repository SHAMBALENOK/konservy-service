from flask import Flask
from routers.rootnhealth import rootnhealth_page

app = Flask(__name__)
app.register_blueprint(rootnhealth_page, url_prefix='/rootnhealth')

if __name__ == '__main__':
  app.run(debug=True)
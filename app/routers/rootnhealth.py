from json import JSONDecodeError
from flask import Flask, request, jsonify, redirect, url_for, render_template, Blueprint, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

rootnhealth_page = Blueprint('rootnhealth_page', __name__,
                             template_folder='templates')


@rootnhealth_page.route('/')
@rootnhealth_page.route('/ping', methods=['GET'])
def ping():
    try:
        return jsonify({
            "status": "OK",
        }), 200

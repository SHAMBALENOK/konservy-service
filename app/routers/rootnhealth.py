from json import JSONDecodeError
from flask import Flask, request, jsonify, redirect, url_for, render_template, Blueprint, abort, FastAPI, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

rootnhealth_page = Blueprint('rootnhealth_page', __name__,
                             template_folder='templates')

APP_NAME = "Banking API"
APP_VERSION = "1.0.0"
API_DESCRIPTION = "Production-Ready Banking API built with FastAPI"

class ApiInfo(BaseModel):
    """Schema for API information response."""
    name: str = Field(..., description="Application name")
    version: str = Field(..., description="API version")
    description: str = Field(..., description="API description")
    docs: str = Field(..., description="Swagger UI documentation URL")
    redoc: str = Field(..., description="ReDoc documentation URL")
    openapi: str = Field(..., description="OpenAPI schema URL")
    health: str = Field(..., description="Health check endpoint URL")
    api_prefix: str = Field(..., description="API base path")

@rootnhealth_page.route('/ping', methods=['GET'])
async def ping():
    return jsonify({
        "status": "OK",
    }), 200

@rootnhealth_page.route('/', methods=['GET'])
async def api_info() -> ApiInfo:
    """Root endpoint with API information."""
    return ApiInfo(
        name="Banking API",
        version="1.0.0",
        description="Production-Ready Banking API built with FastAPI",
        docs="/docs",
        redoc="/redoc",
        openapi="/openapi.json",
        health="/health",
        api_prefix="/api/v1",
    )

@rootnhealth_page.route('/', methods=['GET'])
async def create_openapi_schema():
    """Генерирует базовую схему OpenAPI 3.0.0 вручную."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": APP_NAME,
            "version": APP_VERSION,
            "description": API_DESCRIPTION
        },
        "paths": {
            "/": {
                "get": {
                    "summary": "Get API Info",
                    "operationId": "get_api_info_root",
                    "responses": {"200": {"description": "Successful Response"}}
                }
            },
            "/health": {
                "get": {
                    "summary": "Health Check",
                    "operationId": "health_check",
                    "responses": {"200": {"description": "Successful Response"}}
                }
            }
        },
        "components": {"schemas": {}},
        "tags": []
    }

@rootnhealth_page.route('/openapi.json', methods=['GET'])
async def get_openapi_json():
    """Возвращает схему OpenAPI в формате JSON."""
    schema = create_openapi_schema()
    return jsonify(schema)

@rootnhealth_page.route('/docs', methods=['GET'])
async def get_swagger_ui():
    """Возвращает Swagger UI интерфейс."""
    swagger_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{APP_NAME} - Swagger UI</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.5.0/swagger-ui.css" />
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@4.5.0/swagger-ui-bundle.js"></script>
        <script>
            window.onload = function() {{
                const ui = SwaggerUIBundle({{
                    url: "/openapi.json",
                    dom_id: '#swagger-ui',
                    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
                    layout: "BaseLayout"
                }});
            }};
        </script>
    </body>
    </html>
    """
    return Response(swagger_html, mimetype="text/html")

@rootnhealth_page.route("/redoc", methods=['GET'])
async def get_redoc():
    """Возвращает ReDoc интерфейс."""
    redoc_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{APP_NAME} - ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
        <style>body {{ margin: 0; padding: 0; }}</style>
    </head>
    <body>
        <redoc spec-url="/openapi.json"></redoc>
        <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
    return Response(redoc_html, mimetype="text/html")
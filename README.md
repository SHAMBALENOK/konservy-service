# Banking API - Production-Ready FastAPI Backend

## 📖 Documentation

- [Full API Documentation](docs/full-documentation.md)
- [Project Simplification Suggestions](SIMPLIFICATION_SUGGESTIONS.md)

## 🚀 Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables (see `.env.example`)
3. Run migrations: `alembic upgrade head`
4. Start the server: `uvicorn app.main:app --reload`

## 🐳 Docker Deployment

```bash
docker-compose up -d
```

## ☁️ Render Deployment

See [render.yaml](render.yaml) for configuration.

## 📁 Project Structure

See [docs/full-documentation.md](./docs/full-documentation.md) for detailed structure.

## 🔧 Development

- Run tests: `pytest`
- Code formatting: `black .`
- Linting: `flake8 .`

## 📄 License

See [LICENSE](LICENSE) for details.
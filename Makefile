run:
	docker compose up --build

migrate:
	docker compose run --rm api alembic upgrade head

test:
	cd beta_backend && PYTHONPATH=. pytest -q

smoke:
	cd beta_backend && PYTHONPATH=. python smoke_live.py


up:
	docker compose up -d
	docker exec -i slop-postgres psql -U dev -d slop < init.sql
	@echo "Infrastructure is UP. Kafka :9092, Postgres :5435, Redis :6379"

up-all:
	docker compose up -d --build
	docker exec -i slop-postgres psql -U dev -d slop < init.sql
	@echo "FULL STACK is UP: infra + api-gateway :8000 + aggregator + decision-engine"

status:
	docker compose ps

logs:
	docker compose logs -f api-gateway aggregator decision-engine

psql:
	docker exec -it slop-postgres psql -U dev -d slop

down:
	docker compose down
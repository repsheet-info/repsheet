
DATA_DIR = repsheet_backend/data
DATA_BUCKET = gs://repsheet-data
APP_DIST_BUCKET = gs://repsheet-app-prod-dist
DB_FILENAME = repsheet.sqlite

data-upload:
	gcloud storage rsync -R $(DATA_DIR) $(DATA_BUCKET) 

data-download:
	gcloud storage rsync -R $(DATA_BUCKET) $(DATA_DIR)

db-upload:
	gcloud storage cp ./$(DB_FILENAME) $(DATA_BUCKET)/$(DB_FILENAME)

db-download:
	gcloud storage cp $(DATA_BUCKET)/$(DB_FILENAME) ./$(DB_FILENAME)

db-build:
	python -m repsheet_backend.scripts.build_db

db-add-summaries:
	python -m repsheet_backend.scripts.add_summaries

photos-download:
	python -m repsheet_backend.scripts.download_photos

app-push:
	gcloud storage rsync \
		--recursive \
		--delete-unmatched-destination-objects \
		repsheet_frontend/dist \
		$(APP_DIST_BUCKET) 
	gsutil -m setmeta -h "Cache-Control: max-age=300, public" $(APP_DIST_BUCKET)/**/*
	gsutil -m setmeta -h "Cache-Control: public, max-age=604800, immutable" $(APP_DIST_BUCKET)/_astro/**/*

app-build:
	cd repsheet_frontend && pnpm build

app-dev:
	cd repsheet_frontend && pnpm dev

backend-format:
	black --line-length=100 repsheet_backend

all: db-build db-add-summaries app-build app-push
	
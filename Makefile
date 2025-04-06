
DATA_DIR = repsheet_backend/data
DATA_BUCKET = gs://repsheet-data
DB_FILENAME = repsheet.sqlite

data-upload:
	gcloud storage rsync -R $(DATA_DIR) $(DATA_BUCKET) 

data-download:
	gcloud storage rsync -R $(DATA_BUCKET) $(DATA_DIR)

db-upload:
	gcloud storage cp ./$(DB_FILENAME) $(DATA_BUCKET)/$(DB_FILENAME)

db-download:
	gcloud storage cp $(DATA_BUCKET)/$(DB_FILENAME) ./$(DB_FILENAME)


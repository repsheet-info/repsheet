
DATA_DIR = backend/data
DATA_BUCKET = gs://repsheet-data

data-upload:
	gcloud storage rsync -R $(DATA_DIR) $(DATA_BUCKET) 

data-download:
	gcloud storage rsync -R $(DATA_BUCKET) $(DATA_DIR)


pipeline:
	python run_pipeline.py
sample:
	python run_pipeline.py --sample
test:
	python -m unittest discover tests -v

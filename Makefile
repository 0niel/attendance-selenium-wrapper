fmt: format
format:
	isort --force-single-line-imports app
	black app
	isort app
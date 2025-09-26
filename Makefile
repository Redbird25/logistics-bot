.PHONY: lint format test api bot collector cleanup

lint:
	ruff check src tests

format:
	black src tests
	isort src tests

mypy:
	mypy src

test:
	pytest -q

api:
	python -m logistics_bot.cli api

bot:
	python -m logistics_bot.cli bot

collector:
	python -m logistics_bot.cli collector

cleanup:
	python -m logistics_bot.cli cleanup

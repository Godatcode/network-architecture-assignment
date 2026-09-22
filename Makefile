.PHONY: test demo clean

test:
	python3 -m unittest discover -s tests -v

demo:
	@echo "Terminal 1: ./bserve ./www 9000"
	@echo "Terminal 2: ./bcurl -v localhost:9000/index.html"

clean:
	find . -type d -name __pycache__ -prune -exec rm -r {} +
